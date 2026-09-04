import logging

import requests
from celery import shared_task

from .addBalance import update_rooms_from_json

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def fetch_data_from_api(self, url: str):
    """
    Stáhne výpis transakcí z bankovního API a propíše ho do zůstatků pokojů.
    """
#    try:
#        response = requests.get(url, timeout=15)
#        response.raise_for_status()
#    except requests.RequestException as exc:
#        logger.warning("Stažení bankovních dat selhalo (%s): %s", url, exc)
#        raise self.retry(exc=exc)
#
#    try:
#        update_rooms_from_json(response.text)
#  except Exception:
#       logger.exception("Zpracování bankovních dat selhalo pro odpověď z %s", url)
#        raise
    with open(url, "r", encoding="utf-8") as file:
         data = file.read()
    update_rooms_from_json(data)

