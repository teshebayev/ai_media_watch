"""Прогон LLM-слоя (scenario detection) на GPU через transformers — без vLLM-сервера.

На этом хосте docker без nvidia-container-toolkit (vLLM в контейнере не поднять), а
хост-сервер песочница убивает. Поэтому LLM крутим in-process на GPU: тот же системный
промпт, что в backend/app/services/scenario.py, та же задача — combined_text → JSON
{fraud_type, confidence, risk_signals, evidence_spans}.

Модель: Qwen2.5-3B-Instruct (bf16, ~6 ГБ) — влезает в свободную память рядом с serve_b1k.
"""

import json
import re
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from backend.app.services.scenario import SYSTEM_PROMPT

MODEL = "Qwen/Qwen2.5-3B-Instruct"

EXAMPLES = [
    ("gambling/ru", "Регистрируйся на casino-x.com, вводи промокод PROMO777 и получи бонус на депозит. Я поднял 500 000 ₸, вывод работает!"),
    ("egov_call/ru", "Здравствуйте, вам доставка от eGov. Назовите код из SMS. Теперь с вами сотрудник КНБ, на вас оформляют кредит, переведите деньги на безопасный счёт, никому не говорите."),
    ("pyramid/ru", "Инвестируй 10 000 ₸ и получай 20% в неделю. Пригласи друзей, повышай уровень — чем больше команда, тем выше доход."),
    ("phishing/ru", "Ваш аккаунт заблокирован. Перейдите по ссылке и подтвердите данные карты и код из SMS, иначе списание."),
    ("egov_call/kk", "Сәлеметсіз бе, сізге eGov жеткізілімі келді. SMS кодын айтыңыз. Ұлттық банк қызметкері, ақшаны қауіпсіз шотқа аударыңыз, ешкімге айтпаңыз."),
    ("legit/ru", "Депозит в Halyk Bank под 14% годовых, страхование вкладов до 20 млн ₸. Оформление в приложении."),
]


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"_raw": text[:200]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"_raw": text[:200]}


def main():
    print(f"Загрузка {MODEL} на GPU…")
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16).to("cuda:0")
    model.eval()
    print(f"  модель загружена за {time.time() - t0:.0f} c, "
          f"GPU занято: {torch.cuda.memory_allocated() / 1e9:.1f} ГБ\n")

    for tag, text in EXAMPLES:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        t = time.time()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=256, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        gen = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        dt = time.time() - t
        j = extract_json(gen)
        print(f"[{tag}]  ({dt:.1f}c)")
        print(f"   fraud_type : {j.get('fraud_type')}  conf={j.get('confidence')}")
        print(f"   signals    : {j.get('risk_signals')}")
        print(f"   evidence   : {j.get('evidence_spans')}")
        print()
    print("LLM_GPU_OK")


if __name__ == "__main__":
    main()
