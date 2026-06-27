"""Alert routing and notification system."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from .anomaly import Alert, AlertSeverity


class NotificationChannel(str, Enum):
    """Available notification channels."""

    WINDOWS_TOAST = "windows_toast"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    LOG = "log"


@dataclass
class NotificationConfig:
    """Configuration for a notification channel."""

    channel: NotificationChannel
    enabled: bool = True
    min_severity: AlertSeverity = AlertSeverity.INFO
    rate_limit_seconds: int = 60  # Don't send duplicate alerts within this window
    template: str | None = None  # Custom message template


class AlertRouter:
    """
    Route alerts to appropriate notification channels.

    Features:
    - Multiple channel support
    - Severity-based filtering
    - Rate limiting
    - Custom templates
    """

    def __init__(self):
        self._channels: dict[NotificationChannel, NotificationConfig] = {
            NotificationChannel.LOG: NotificationConfig(channel=NotificationChannel.LOG),
            NotificationChannel.WINDOWS_TOAST: NotificationConfig(
                channel=NotificationChannel.WINDOWS_TOAST,
                min_severity=AlertSeverity.WARNING,
            ),
        }
        self._handlers: dict[NotificationChannel, Callable] = {}
        self._last_sent: dict[str, datetime] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default notification handlers."""

        async def log_handler(alert: Alert, config: NotificationConfig) -> None:
            """Log alerts to console/file."""
            import logging

            logger = logging.getLogger("omniagent.alerts")
            log_method = logger.warning if alert.severity == AlertSeverity.WARNING else logger.error

            log_method(
                f"[{alert.severity.value.upper()}] {alert.metric}: {alert.message} "
                f"(value: {alert.current_value}, threshold: {alert.threshold_value})"
            )

        self._handlers[NotificationChannel.LOG] = log_handler

        async def windows_toast_handler(alert: Alert, config: NotificationConfig) -> None:
            """Send Windows Toast notifications."""
            try:
                # Try using winotify
                from winotify import Notification, audio

                toast = Notification(
                    app_id="Win11-OmniAgent",
                    title=f"{alert.severity.value.upper()}: {alert.metric}",
                    msg=alert.message,
                    duration="short",
                )
                toast.show()
            except ImportError:
                # Fallback to PowerShell toast
                import subprocess

                title = f"{alert.severity.value.upper()}: {alert.metric}"
                script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $text = $xml.GetElementsByTagName("text")
                $text[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null
                $text[1].AppendChild($xml.CreateTextNode("{alert.message}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Win11-OmniAgent").Show($toast)
                '''
                subprocess.run(["powershell", "-Command", script], capture_output=True)

        self._handlers[NotificationChannel.WINDOWS_TOAST] = windows_toast_handler

    def configure_channel(
        self,
        channel: NotificationChannel,
        enabled: bool = True,
        min_severity: AlertSeverity = AlertSeverity.INFO,
        rate_limit_seconds: int = 60,
    ) -> None:
        """Configure a notification channel."""
        self._channels[channel] = NotificationConfig(
            channel=channel,
            enabled=enabled,
            min_severity=min_severity,
            rate_limit_seconds=rate_limit_seconds,
        )

    def register_handler(self, channel: NotificationChannel, handler: Callable) -> None:
        """Register a custom handler for a channel."""
        self._handlers[channel] = handler

    async def send_alert(self, alert: Alert) -> None:
        """Send an alert to all configured channels."""
        # Check rate limiting
        rate_key = f"{alert.id}:{alert.severity.value}"
        now = datetime.now()

        if rate_key in self._last_sent:
            for channel, config in self._channels.items():
                if config.enabled and alert.severity.value >= config.min_severity.value:
                    last_sent = self._last_sent.get(f"{channel.value}:{rate_key}")
                    if last_sent and (now - last_sent).total_seconds() < config.rate_limit_seconds:
                        return  # Rate limited

        # Queue the alert
        await self._queue.put(alert)

    async def _process_queue(self) -> None:
        """Process queued alerts."""
        while self._running:
            try:
                alert = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                for channel, config in self._channels.items():
                    if not config.enabled:
                        continue

                    if alert.severity.value < config.min_severity.value:
                        continue

                    if channel in self._handlers:
                        try:
                            handler = self._handlers[channel]
                            if asyncio.iscoroutinefunction(handler):
                                await handler(alert, config)
                            else:
                                handler(alert, config)

                            # Update rate limit tracking
                            rate_key = f"{channel.value}:{alert.id}:{alert.severity.value}"
                            self._last_sent[rate_key] = datetime.now()
                        except Exception:
                            pass

            except asyncio.TimeoutError:
                continue
            except Exception:
                pass

    async def start(self) -> None:
        """Start the alert router."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_queue())

    async def stop(self) -> None:
        """Stop the alert router."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_stats(self) -> dict:
        """Get alert routing statistics."""
        return {
            "queue_size": self._queue.qsize(),
            "channels": {
                channel.value: {
                    "enabled": config.enabled,
                    "min_severity": config.min_severity.value,
                    "rate_limit_seconds": config.rate_limit_seconds,
                }
                for channel, config in self._channels.items()
            },
        }


class WebhookNotifier:
    """Send alerts to webhooks."""

    def __init__(self):
        self._webhooks: list[dict] = []

    def add_webhook(
        self,
        url: str,
        method: str = "POST",
        headers: dict | None = None,
        template: str | None = None,
    ) -> str:
        """Add a webhook endpoint."""
        import uuid

        webhook_id = str(uuid.uuid4())
        self._webhooks.append({
            "id": webhook_id,
            "url": url,
            "method": method,
            "headers": headers or {},
            "template": template or self._default_template(),
        })
        return webhook_id

    def remove_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook."""
        for i, wh in enumerate(self._webhooks):
            if wh["id"] == webhook_id:
                self._webhooks.pop(i)
                return True
        return False

    def _default_template(self) -> str:
        """Get default webhook template."""
        return json.dumps({
            "alert": {
                "id": "{{alert.id}}",
                "severity": "{{alert.severity}}",
                "metric": "{{alert.metric}}",
                "message": "{{alert.message}}",
                "current_value": "{{alert.current_value}}",
                "threshold_value": "{{alert.threshold_value}}",
                "timestamp": "{{alert.timestamp}}",
            }
        })

    async def notify(self, alert: Alert) -> dict:
        """Send alert to all webhooks."""
        results = []

        for webhook in self._webhooks:
            try:
                result = await self._send_webhook(alert, webhook)
                results.append({
                    "webhook_id": webhook["id"],
                    "success": result["success"],
                    "status_code": result.get("status_code"),
                })
            except Exception as e:
                results.append({
                    "webhook_id": webhook["id"],
                    "success": False,
                    "error": str(e),
                })

        return {"results": results}

    async def _send_webhook(self, alert: Alert, webhook: dict) -> dict:
        """Send alert to a single webhook."""
        import httpx

        # Format template
        content = webhook["template"]
        content = content.replace("{{alert.id}}", alert.id)
        content = content.replace("{{alert.severity}}", alert.severity.value)
        content = content.replace("{{alert.metric}}", alert.metric)
        content = content.replace("{{alert.message}}", alert.message)
        content = content.replace("{{alert.current_value}}", str(alert.current_value))
        content = content.replace("{{alert.threshold_value}}", str(alert.threshold_value))
        content = content.replace("{{alert.timestamp}}", alert.timestamp.isoformat())

        headers = webhook.get("headers", {})
        headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    method=webhook["method"],
                    url=webhook["url"],
                    headers=headers,
                    content=content,
                )
                return {
                    "success": 200 <= response.status_code < 300,
                    "status_code": response.status_code,
                }
        except httpx.TimeoutException:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class EmailNotifier:
    """Send alerts via email."""

    def __init__(self):
        self._smtp_config: dict | None = None
        self._recipients: list[str] = []

    def configure(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        use_tls: bool = True,
    ) -> None:
        """Configure SMTP settings."""
        self._smtp_config = {
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
            "password": smtp_password,
            "use_tls": use_tls,
        }

    def add_recipient(self, email: str) -> None:
        """Add an email recipient."""
        if email not in self._recipients:
            self._recipients.append(email)

    def remove_recipient(self, email: str) -> bool:
        """Remove an email recipient."""
        if email in self._recipients:
            self._recipients.remove(email)
            return True
        return False

    async def notify(self, alert: Alert) -> dict:
        """Send alert via email."""
        if not self._smtp_config or not self._recipients:
            return {"success": False, "error": "Email not configured or no recipients"}

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg["Subject"] = f"[{alert.severity.value.upper()}] Win11-OmniAgent: {alert.metric}"
            msg["From"] = self._smtp_config["user"]

            body = f"""
            Alert from Win11-OmniAgent

            Severity: {alert.severity.value.upper()}
            Metric: {alert.metric}
            Message: {alert.message}

            Current Value: {alert.current_value}
            Threshold: {alert.threshold_value}
            Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

            Alert ID: {alert.id}
            """

            msg.attach(MIMEText(body, "plain"))
            msg["To"] = ", ".join(self._recipients)

            # Send email
            with smtplib.SMTP(self._smtp_config["host"], self._smtp_config["port"]) as server:
                if self._smtp_config["use_tls"]:
                    server.starttls()
                if self._smtp_config["user"]:
                    server.login(self._smtp_config["user"], self._smtp_config["password"])
                server.sendmail(self._smtp_config["user"], self._recipients, msg.as_string())

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}