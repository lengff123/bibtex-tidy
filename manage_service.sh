#!/bin/bash

case "$1" in
    start)
        echo "Starting BibTeX service..."
        /home/bib_tidy/venv/bin/python /home/bib_tidy/web/app.py &
        ;;
    stop)
        echo "Stopping BibTeX service..."
        pkill -f "python.*app.py"
        ;;
    status)
        if pgrep -f "python.*app.py" > /dev/null; then
            echo "BibTeX service is running"
        else
            echo "BibTeX service is not running"
        fi
        ;;
    restart)
        echo "Restarting BibTeX service..."
        pkill -f "python.*app.py"
        sleep 2
        /home/bib_tidy/venv/bin/python /home/bib_tidy/web/app.py &
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
