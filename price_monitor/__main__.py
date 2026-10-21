import argparse
import logging
import sys

from price_monitor.config import load_config
from price_monitor.notify import format_changes, send_telegram
from price_monitor.report import build_report
from price_monitor.scraper import crawl, make_client
from price_monitor.storage import Storage

log = logging.getLogger("price_monitor")


def cmd_run(args) -> int:
    config = load_config(args.config)
    storage = Storage(config.settings.db_path)
    items, failed = [], []
    with make_client(config.settings) as client:
        for source in config.sources:
            try:
                found = list(crawl(source, config.settings, client))
            except Exception as e:  # один упавший сайт не должен ронять весь запуск
                log.error("[%s] ошибка: %s", source.name, e)
                failed.append(source.name)
                continue
            log.info("[%s] собрано товаров: %s", source.name, len(found))
            items.extend(found)

    changes = storage.save(items)
    new = sum(c.is_new for c in changes)
    log.info("Всего товаров: %s, новых: %s, изменилось: %s", len(items), new, len(changes) - new)

    if args.report:
        log.info("Отчёт: %s", build_report(storage, args.report, changes))
    if not args.no_notify:
        text = format_changes(changes, config.settings.notify_threshold)
        if text:
            send_telegram(config.settings, text)
    storage.close()
    return 1 if failed and not items else 0


def cmd_report(args) -> int:
    config = load_config(args.config)
    storage = Storage(config.settings.db_path)
    log.info("Отчёт: %s", build_report(storage, args.output))
    storage.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="price_monitor", description="Мониторинг цен на сайтах")
    parser.add_argument("-c", "--config", default="sources.toml", help="файл с источниками (по умолчанию sources.toml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="собрать цены, сохранить историю, уведомить об изменениях")
    run.add_argument("--report", metavar="FILE.xlsx", help="сразу выгрузить отчёт в Excel")
    run.add_argument("--no-notify", action="store_true", help="не отправлять уведомление в Telegram")
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="выгрузить отчёт в Excel из накопленной истории")
    rep.add_argument("-o", "--output", default="reports/prices.xlsx")
    rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
