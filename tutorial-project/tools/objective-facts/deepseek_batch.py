#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deepseek_batch.py —— OpenAI Chat Completions 兼容接口的批处理工具

从原科研工作流中提取的可移植版本。默认配置兼容 DeepSeek，也可以通过
配置文件或 MODEL_* 环境变量连接其它 OpenAI 兼容接口。
当主对话面临以下场景时优先调用本脚本（成本远低于 Claude）：
  - >5 个独立的同模板任务（如批量文献事实抽取、批量代码改写）
  - 累计输出 >50K tokens
  - 不需要工具调用或多轮对话
  - 不属于"单篇深度梳理 / 直接 Q&A"

实际发送文献内容前必须显式传入 `--yes-send`；`--dry-run` 不需要 API key，
也不会访问网络。

=============================================
用法 1: 单 prompt 模板 × 多输入文件（主用法）
=============================================
  py -3.11 deepseek_batch.py \\
      --prompt-file prompt.txt \\
      --inputs file1.md file2.md file3.md \\
      --output-dir reports/ \\
      --output-suffix _报告.md \\
      --model deepseek-v4-flash \\
      --concurrency 8

  prompt.txt 内 {INPUT} 占位符会被每个输入文件的内容替换。
  输出文件名 = <input_stem><suffix>，放在 --output-dir 下。
  额外占位符: {STEM} = 输入文件名（不含扩展名）, {PATH} = 完整路径。

=============================================
用法 2: 直接 inline prompt（调试/试用）
=============================================
  py -3.11 deepseek_batch.py \\
      --prompt-text "Summarize the following:\\n\\n{INPUT}" \\
      --inputs paper.md \\
      --output-dir out/

=============================================
用法 3: 任务 JSON（高级，异构 prompt）
=============================================
  jobs.json: [{"prompt": "...", "input_file": "...", "output_file": "..."}, ...]
  py -3.11 deepseek_batch.py --jobs jobs.json

=============================================
配置（deepseek_config.json 同目录）
=============================================
  {
    "api_key": "",
    "endpoint": "https://api.deepseek.com/v1/chat/completions",
    "default_model": "deepseek-v4-flash"
  }
  Workmode Public 已配置的模型环境变量优先；也支持 MODEL_* / DEEPSEEK_*。
  不要把 key 写死在脚本里；同步盘环境注意 config 文件别提交到公网。

环境：Python 3.11+ 标准库（urllib + concurrent.futures + argparse）。无需 pip。
"""

import sys
import os
import json
import time
import argparse
import logging
from pathlib import Path
from urllib import request, error
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 常量 =====

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = TOOL_DIR / "deepseek_config.json"

# 模型价格会变化，分发版不内置可能过期的价格。需要估算时可在本地扩展此表。
PRICING: dict[str, dict[str, float]] = {}

# 兼容旧模型 ID
MODEL_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
    "flash": "deepseek-v4-flash",
    "pro": "deepseek-v4-pro",
}


def load_dotenv(path: Path) -> None:
    """简易 .env 加载器：把 KEY=VALUE 行注入 os.environ（已存在的不覆盖）"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Path, *, require_api_key: bool = True) -> dict:
    """读 config + .env + 环境变量覆盖"""
    # 1) 先尝试加载同目录的 .env（不覆盖已设的环境变量）
    load_dotenv(TOOL_DIR / ".env")

    cfg = {
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "default_model": "deepseek-v4-flash",
    }
    # 2) JSON 配置文件
    if path.exists():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    # 3) 环境变量优先级最高
    env_key = (
        os.environ.get("MODEL_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("WORKMODE_MODEL_API_KEY")
    )
    if env_key:
        cfg["api_key"] = env_key
    env_endpoint = os.environ.get("MODEL_ENDPOINT") or os.environ.get("DEEPSEEK_ENDPOINT")
    workmode_base = os.environ.get("WORKMODE_MODEL_BASE_URL")
    if not env_endpoint and workmode_base:
        env_endpoint = workmode_base.rstrip("/") + "/chat/completions"
    if env_endpoint:
        cfg["endpoint"] = env_endpoint
    env_model = os.environ.get("MODEL_NAME") or os.environ.get("WORKMODE_MODEL_NAME")
    if env_model:
        cfg["default_model"] = env_model
    if require_api_key and not cfg.get("api_key"):
        sys.exit(
            "未找到模型 API key：请复制 deepseek_config.example.json 为 "
            "deepseek_config.json 并仅在本机填写，或设置 MODEL_API_KEY / "
            "DEEPSEEK_API_KEY。"
        )
    return cfg


def call_api(prompt: str, *, model: str, api_key: str, endpoint: str,
             max_tokens: int | None = None, temperature: float = 0.3,
             retries: int = 3, timeout: int = 300) -> dict:
    """调一次 DeepSeek Chat Completions API；指数退避重试瞬时错误。

    max_tokens=None（默认）→ 不发送 max_tokens 字段，由 API 决定（V4 系列上限 384K）。
    仅在需要显式压缩输出时才设值。
    """
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    payload = json.dumps(body).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_err = None
    for attempt in range(retries):
        try:
            req = request.Request(endpoint, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except error.HTTPError as e:
            # 4xx 客户端错误一般不重试
            body = e.read().decode("utf-8", errors="ignore")
            if 400 <= e.code < 500 and e.code not in (408, 429):
                raise RuntimeError(f"HTTPError {e.code}: {body[:500]}") from None
            last_err = f"HTTP {e.code}: {body[:300]}"
        except (error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"

        if attempt < retries - 1:
            sleep_s = 2 ** attempt
            logging.warning(f"  重试 {attempt+1}/{retries}（{sleep_s}s 后）：{last_err}")
            time.sleep(sleep_s)

    raise RuntimeError(f"重试 {retries} 次后失败：{last_err}")


def extract_content_and_usage(resp: dict) -> tuple:
    """从 API 响应里取出文本 + token 用量"""
    content = resp["choices"][0]["message"]["content"]
    usage = resp.get("usage", {})
    return content, {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "cache_hit_tokens": usage.get("prompt_cache_hit_tokens", 0),
    }


def estimate_cost(usage: dict, model: str) -> float | None:
    """根据 usage + 模型价表估算 USD 成本"""
    price = PRICING.get(model)
    if not price:
        return None
    return (usage["input_tokens"] / 1e6) * price["input"] + \
           (usage["output_tokens"] / 1e6) * price["output"]


def render_prompt(template: str, *, content: str, stem: str, path: str) -> str:
    """把 {INPUT}/{STEM}/{PATH} 占位符替换"""
    return template.replace("{INPUT}", content).replace("{STEM}", stem).replace("{PATH}", path)


def build_jobs_from_inputs(prompt_template: str, input_paths: list,
                           output_dir: Path, output_suffix: str) -> list:
    """单 prompt × 多输入 → job list"""
    jobs = []
    for p in input_paths:
        p = Path(p).resolve()
        if not p.exists():
            logging.error(f"输入不存在：{p}")
            continue
        stem = p.stem
        content = p.read_text(encoding="utf-8", errors="replace")
        rendered = render_prompt(prompt_template, content=content, stem=stem, path=str(p))
        out_path = output_dir / f"{stem}{output_suffix}"
        jobs.append({
            "id": stem,
            "input_file": str(p),
            "output_file": str(out_path),
            "prompt": rendered,
        })
    return jobs


def build_jobs_from_json(jobs_json: Path) -> list:
    """jobs.json 加载（每条含 prompt / input_file / output_file）"""
    raw = json.loads(jobs_json.read_text(encoding="utf-8"))
    jobs = []
    for i, j in enumerate(raw):
        prompt = j["prompt"]
        if "input_file" in j and j["input_file"]:
            p = Path(j["input_file"]).resolve()
            content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
            prompt = render_prompt(prompt, content=content, stem=p.stem, path=str(p))
        jobs.append({
            "id": j.get("id", f"job{i}"),
            "input_file": j.get("input_file", ""),
            "output_file": j["output_file"],
            "prompt": prompt,
        })
    return jobs


def run_one_job(job: dict, *, model: str, api_cfg: dict,
                max_tokens: int | None, temperature: float,
                retries: int, timeout: int, resume: bool) -> dict:
    """单 job 执行：调 API → 写文件 → 返回 manifest 行"""
    jid = job["id"]
    out = Path(job["output_file"])

    if resume and out.exists() and out.stat().st_size > 0:
        logging.info(f"[SKIP] {jid} （--resume，输出已存在）")
        return {"id": jid, "status": "skipped", "output_file": str(out)}

    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        resp = call_api(job["prompt"], model=model,
                        api_key=api_cfg["api_key"], endpoint=api_cfg["endpoint"],
                        max_tokens=max_tokens, temperature=temperature,
                        retries=retries, timeout=timeout)
        content, usage = extract_content_and_usage(resp)
        out.write_text(content, encoding="utf-8")
        elapsed = time.time() - t0
        cost = estimate_cost(usage, model)
        cost_label = f"  cost≈${cost:.4f}" if cost is not None else ""
        logging.info(f"[DONE] {jid:30s}  in={usage['input_tokens']:6d}  out={usage['output_tokens']:6d}{cost_label}  {elapsed:.1f}s")
        result = {
            "id": jid, "status": "ok", "output_file": str(out),
            "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"],
            "elapsed_s": round(elapsed, 1),
        }
        if cost is not None:
            result["cost_usd"] = cost
        return result
    except Exception as e:
        elapsed = time.time() - t0
        logging.error(f"[FAIL] {jid}：{e}")
        return {
            "id": jid, "status": "error", "output_file": str(out),
            "error": str(e)[:500], "elapsed_s": round(elapsed, 1),
        }


def main():
    ap = argparse.ArgumentParser(
        description="OpenAI Chat Completions 兼容接口批处理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="详见本目录 README.md；发送前先用 --dry-run 检查任务。",
    )
    # Prompt 来源（三选一）
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt-file", type=Path, help="prompt 模板文件（含 {INPUT} 占位符）")
    g.add_argument("--prompt-text", type=str, help="直接 inline prompt 模板（含 {INPUT}）")
    g.add_argument("--jobs", type=Path, help="任务 JSON（每条含 prompt/input_file/output_file）")

    # 输入 / 输出
    ap.add_argument("--inputs", nargs="+", type=str, help="输入文件列表（配合 --prompt-* 用）")
    ap.add_argument("--output-dir", type=Path, default=Path("."), help="输出目录")
    ap.add_argument("--output-suffix", type=str, default=".out.md", help="输出文件后缀（默认 .out.md）")

    # 模型 / 调用参数
    ap.add_argument("--model", type=str, default=None, help="deepseek-v4-flash (默认) / deepseek-v4-pro / 别名: flash, pro")
    ap.add_argument("--concurrency", type=int, default=8, help="并发线程数（默认 8）")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="单次最大输出 token（默认不发送，由 API 决定；V4 系列上限 384K）。"
                         "仅在需要显式压缩输出时才设值。")
    ap.add_argument("--temperature", type=float, default=0.3, help="默认 0.3（事实抽取偏低温）")
    ap.add_argument("--retry", type=int, default=3, help="失败重试次数（指数退避）")
    ap.add_argument("--timeout", type=int, default=300, help="单次请求超时秒")

    # 控制
    ap.add_argument("--resume", action="store_true", help="跳过输出已存在的 job（断点续跑）")
    ap.add_argument("--dry-run", action="store_true", help="不调用 API，只打印 plan")
    ap.add_argument("--yes-send", action="store_true",
                    help="确认把输入文献内容发送到配置的模型服务；缺少时拒绝联网")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"配置文件（默认 {DEFAULT_CONFIG.name}）")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--manifest", type=Path, default=None, help="batch_manifest.json 路径（默认 output-dir 下）")

    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    if not args.dry_run and not args.yes_send:
        sys.exit(
            "拒绝发送：本命令会把输入文件内容发送到外部模型服务。"
            "确认后重新运行并加入 --yes-send。"
        )

    # dry-run 允许在没有 key 的情况下检查任务、路径和大致输入量。
    api_cfg = load_config(args.config, require_api_key=not args.dry_run)
    model = MODEL_ALIASES.get(args.model, args.model) or api_cfg.get("default_model", "deepseek-v4-flash")
    if model not in PRICING:
        logging.warning(f"未知模型 {model}（不在价表里，cost 估算为 0）")

    # 构造 jobs
    if args.jobs:
        jobs = build_jobs_from_json(args.jobs)
    else:
        if not args.inputs:
            sys.exit("必须给 --inputs（除非走 --jobs 模式）")
        if args.prompt_file:
            tpl = args.prompt_file.read_text(encoding="utf-8")
        else:
            tpl = args.prompt_text
        if "{INPUT}" not in tpl:
            logging.warning("prompt 模板里没找到 {INPUT} 占位符（确认是否故意？）")
        jobs = build_jobs_from_inputs(tpl, args.inputs, args.output_dir, args.output_suffix)

    logging.info(f"模型: {model}    并发: {args.concurrency}    任务数: {len(jobs)}")

    # Dry run: 只打印 plan
    if args.dry_run:
        for j in jobs:
            n_in = len(j["prompt"])
            est_in_tokens = n_in // 4  # 粗略估
            price = PRICING.get(model)
            cost_label = f"  est_input_cost≈${est_in_tokens / 1e6 * price['input']:.4f}" if price else ""
            print(f"[DRY] {j['id']}  prompt_chars={n_in}  est_in_tokens≈{est_in_tokens}{cost_label}  → {j['output_file']}")
        print(f"\n合计 {len(jobs)} jobs。dry-run 不实际调用 API。")
        return

    # 执行
    manifest = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(run_one_job, j, model=model, api_cfg=api_cfg,
                             max_tokens=args.max_tokens, temperature=args.temperature,
                             retries=args.retry, timeout=args.timeout,
                             resume=args.resume): j for j in jobs}
        for fut in as_completed(futures):
            manifest.append(fut.result())
    elapsed = time.time() - t0

    # 写 manifest
    manifest_path = args.manifest or (args.output_dir / "batch_manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    total_in = sum(m.get("input_tokens", 0) for m in manifest)
    total_out = sum(m.get("output_tokens", 0) for m in manifest)
    measured_costs = [m["cost_usd"] for m in manifest if "cost_usd" in m]
    total_cost = sum(measured_costs) if measured_costs else None
    n_ok = sum(1 for m in manifest if m["status"] == "ok")
    n_err = sum(1 for m in manifest if m["status"] == "error")
    n_skip = sum(1 for m in manifest if m["status"] == "skipped")
    summary = {
        "model": model,
        "concurrency": args.concurrency,
        "total_jobs": len(jobs),
        "ok": n_ok, "error": n_err, "skipped": n_skip,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cost_usd": round(total_cost, 4) if total_cost is not None else None,
        "elapsed_s": round(elapsed, 1),
        "jobs": manifest,
    }
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    logging.info(f"=== 批次完成 ===")
    logging.info(f"  成功 {n_ok}    失败 {n_err}    跳过 {n_skip}")
    cost_label = f"  cost≈${total_cost:.4f}" if total_cost is not None else "  cost=未配置价表"
    logging.info(f"  累计 in={total_in}  out={total_out}{cost_label}")
    logging.info(f"  耗时 {elapsed:.1f}s")
    logging.info(f"  manifest: {manifest_path}")

    if n_err > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
