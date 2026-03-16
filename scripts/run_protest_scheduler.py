import signal

from dotenv import load_dotenv

from app import create_app
from app.services.protest_scheduler import (
    run_protest_scheduler_forever,
    stop_protest_scheduler,
)

load_dotenv()


app = create_app()


def _handle_stop(signum, frame):
    stop_protest_scheduler()


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)


if __name__ == "__main__":
    run_protest_scheduler_forever(app)
if __name__ == "__main__":
    run_protest_scheduler_forever(app)
