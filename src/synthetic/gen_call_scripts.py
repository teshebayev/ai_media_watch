"""Этап 8.1 — генератор-комбинатор синтетических сценариев звонков (ru/kk).

Без отдельной казахской LLM: шаблоны × банки фраз из ТЗ §2.4.
Комбинаторика `этап × организация × секрет × pressure-фраза` даёт десятки
уникальных диалогов из одного скрипта. Сценарии строятся ТОЛЬКО на основе
официальных предупреждений eGov/Нацбанка (ТЗ §0, §2.3) — реальные записи не используются.

Выход: kz_call_scripts.csv с колонками id, language, case_type, stage, text
(deliverable Студента 5). Дальше озвучивается src/synthetic/tts_batch.py.

Запуск:
    python -m src.synthetic.gen_call_scripts [--out data/raw/kz_calls/kz_call_scripts.csv]
"""

from __future__ import annotations

import argparse
import csv
import itertools
import os

# Банки подстановок по языкам. stage → (case_type, [шаблоны с {org}/{secret}/{pressure}])
ORGS = {
    "ru": ["eGov", "КНБ", "Нацбанк", "служба безопасности банка"],
    "kk": ["eGov", "ҰҚК", "Ұлттық банк", "банк қауіпсіздік қызметі"],
}
SECRETS = {
    "ru": ["код из SMS", "данные карты", "ЭЦП", "удалённый доступ"],
    "kk": ["SMS кодын", "карта деректерін", "ЭЦҚ", "қашықтан кіруді"],
}
PRESSURE = {
    "ru": ["не кладите трубку", "никому не говорите", "это срочно", "иначе оформят кредит"],
    "kk": ["телефонды қоймаңыз", "ешкімге айтпаңыз", "бұл шұғыл", "әйтпесе несие рәсімделеді"],
}

# Этапы звонка (ТЗ §2.2) → case_type + шаблоны реплик.
STAGES = {
    "ru": [
        ("egov_delivery", "fake_egov_delivery_call",
         "Здравствуйте, вам пришла доставка от {org}. Чтобы получить, назовите {secret}."),
        ("sms_code", "fake_egov_delivery_call",
         "Для подтверждения продиктуйте {secret}, {pressure}."),
        ("authority_escalation", "fake_government_call",
         "С вами говорит сотрудник {org}. Ваши данные скомпрометированы, {pressure}."),
        ("loan_threat", "fake_credit",
         "На вас оформляют кредит. Чтобы отменить, сообщите {secret}, {pressure}."),
        ("safe_account", "fake_government_call",
         "Переведите деньги на безопасный счёт от {org}, {pressure}."),
    ],
    "kk": [
        ("egov_delivery", "fake_egov_delivery_call",
         "Сәлеметсіз бе, сізге {org} жеткізілімі келді. Алу үшін {secret} айтыңыз."),
        ("sms_code", "fake_egov_delivery_call",
         "Растау үшін {secret} айтыңыз, {pressure}."),
        ("authority_escalation", "fake_government_call",
         "Сізбен {org} қызметкері сөйлесіп тұр. Деректеріңіз қауіп астында, {pressure}."),
        ("loan_threat", "fake_credit",
         "Сізге несие рәсімделуде. Тоқтату үшін {secret} хабарлаңыз, {pressure}."),
        ("safe_account", "fake_government_call",
         "Ақшаны {org} қауіпсіз шотына аударыңыз, {pressure}."),
    ],
}


def generate(languages: tuple[str, ...] = ("ru", "kk")) -> list[dict]:
    rows: list[dict] = []
    idx = 0
    for lang in languages:
        for stage, case_type, template in STAGES[lang]:
            needs_org = "{org}" in template
            needs_secret = "{secret}" in template
            needs_pressure = "{pressure}" in template
            orgs = ORGS[lang] if needs_org else [""]
            secrets = SECRETS[lang] if needs_secret else [""]
            pressures = PRESSURE[lang] if needs_pressure else [""]
            seen: set[str] = set()
            for org, secret, pressure in itertools.product(orgs, secrets, pressures):
                text = template.format(org=org, secret=secret, pressure=pressure)
                if text in seen:
                    continue
                seen.add(text)
                idx += 1
                rows.append({
                    "id": f"kzcall_{lang}_{idx:04d}",
                    "language": lang,
                    "case_type": case_type,
                    "stage": stage,
                    "text": text,
                })
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "language", "case_type", "stage", "text"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/raw/kz_calls/kz_call_scripts.csv")
    parser.add_argument("--langs", default="ru,kk")
    args = parser.parse_args()
    rows = generate(tuple(args.langs.split(",")))
    write_csv(rows, args.out)
    print(f"Сгенерировано сценариев: {len(rows)} → {args.out}")


if __name__ == "__main__":
    main()
