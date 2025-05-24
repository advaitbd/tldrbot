from utils.webhook_server import WebhookServer
from handlers.webhook_handlers import WebhookHandlers

def main():
    webhook_handlers = WebhookHandlers()
    webhook_server = WebhookServer(webhook_handlers)
    webhook_server.start()

if __name__ == "__main__":
    main()