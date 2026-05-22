from llm import *
from util.request import get_yesterday_arxiv_papers
from util.construct_email import *
from tqdm import tqdm
import json
import os
from datetime import datetime, timezone
import time
import random
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class ArxivDaily:
    HISTORY_FILE = "arxiv_pushed_ids.json"

    def __init__(
        self,
        categories: list[str],
        max_entries: int,
        max_paper_num: int,
        provider: str,
        model: str,
        base_url,
        api_key,
        description: str,
        num_workers: int,
        temperature: float,
        save_dir,
    ):
        self.model_name = model
        self.base_url = base_url
        self.api_key = api_key
        self.max_paper_num = max_paper_num
        self.save_dir = save_dir
        self.num_workers = num_workers
        self.temperature = temperature
        self.run_datetime = datetime.now(timezone.utc)
        self.run_date = self.run_datetime.strftime("%Y-%m-%d")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = os.path.join(base_dir, save_dir, self.run_date, "json") if save_dir else None
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)

        # Load dedup history
        self.history_path = os.path.join(base_dir, self.HISTORY_FILE)
        self.pushed_ids = self._load_history()

        self.papers = {}
        total_fetched = 0
        for category in categories:
            self.papers[category] = get_yesterday_arxiv_papers(category, max_entries)
            count = len(self.papers[category])
            total_fetched += count
            print(f"{count} papers on arXiv for {category} are fetched.")
            sleep_time = random.randint(5, 15)
            time.sleep(sleep_time)
        self.total_fetched = total_fetched

        # Deduplicate against history
        before = sum(len(v) for v in self.papers.values())
        self._dedup_papers()
        after = sum(len(v) for v in self.papers.values())
        print(f"Dedup: {before} -> {after} papers ({before - after} already pushed).")

        provider = provider.lower()
        if provider == "ollama":
            self.model = Ollama(model)
        elif provider == "openai" or provider == "siliconflow":
            self.model = GPT(model, base_url, api_key)
        else:
            assert False, "Model not supported."
        print(
            "Model initialized successfully. Using {} provided by {}.".format(
                model, provider
            )
        )

        self.description = description
        self.lock = threading.Lock()

    def _load_history(self):
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, OSError):
                return set()
        return set()

    def _save_history(self):
        with self.lock:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self.pushed_ids)), f, ensure_ascii=False, indent=2)

    def _dedup_papers(self):
        for category in self.papers:
            self.papers[category] = [
                p for p in self.papers[category]
                if p["arXiv_id"] not in self.pushed_ids
            ]

    def get_response(self, title, abstract):
        prompt = f"""
你是一个有帮助的学术研究助手，可以帮助我构建每日论文推荐系统。
以下是我最近研究领域的描述：
{self.description}

以下是我从昨天的 arXiv 爬取的论文，我为你提供了标题和摘要：
标题: {title}
摘要: {abstract}

请按以下要求分析这篇论文，并严格按照 JSON 格式返回：
{{
    "chinese_title": "<论文标题的中文翻译>",
    "english_title": "<英文原始标题，即上面的标题>",
    "authors": "<作者列表，用逗号分隔，从摘要中无法获取则填'未知'>",
    "contribution": "<一句话概括论文的核心贡献>",
    "method_summary": "<方法摘要，简要描述论文提出的方法或技术路线>",
    "relevance_reason": "<为什么这篇论文与我的研究兴趣相关>",
    "relevance": <相关性评分，0-10的整数，0完全不相关，10高度相关>,
    "priority": "<阅读优先级：High / Medium / Low>"
}}

使用中文回答。直接返回上述 JSON 格式，无需任何额外解释。
"""

        response = self.model.inference(prompt, temperature=self.temperature)
        return response

    def process_paper(self, paper, max_retries=5):
        retry_count = 0
        cache_path = os.path.join(self.cache_dir, f"{paper['arXiv_id']}.json") if self.cache_dir else None

        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as cache_file:
                    cached_result = json.load(cache_file)
                print(f"Cache hit: {cache_path}")
                return cached_result
            except (json.JSONDecodeError, OSError) as e:
                print(f"Cache read failed {cache_path}: {e}")

        while retry_count < max_retries:
            try:
                title = paper["title"]
                abstract = paper["abstract"]
                response = self.get_response(title, abstract)
                response = response.strip("```").strip("json").strip()
                # Try to extract JSON from response
                if "{" in response:
                    response = response[response.index("{"):]
                if "}" in response:
                    response = response[:response.rindex("}") + 1]
                response = json.loads(response)
                relevance_score = float(response.get("relevance", 0))
                result = {
                    "title": title,
                    "chinese_title": response.get("chinese_title", title),
                    "english_title": response.get("english_title", title),
                    "arXiv_id": paper["arXiv_id"],
                    "abstract": abstract,
                    "authors": response.get("authors", "未知"),
                    "contribution": response.get("contribution", ""),
                    "method_summary": response.get("method_summary", ""),
                    "relevance_reason": response.get("relevance_reason", ""),
                    "summary": response.get("contribution", ""),
                    "relevance_score": relevance_score,
                    "priority": response.get("priority", "Medium"),
                    "pdf_url": paper["pdf_url"],
                    "abstract_url": paper.get("abstract_url", ""),
                }
                if cache_path:
                    try:
                        with self.lock:
                            with open(cache_path, "w", encoding="utf-8") as cache_file:
                                json.dump(result, cache_file, ensure_ascii=False, indent=2)
                    except OSError as write_error:
                        print(f"Cache write failed {cache_path}: {write_error}")
                return result
            except Exception as e:
                retry_count += 1
                print(f"Error processing {paper['arXiv_id']}: {e}")
                print(f"Retry {retry_count}/{max_retries}...")
                if retry_count == max_retries:
                    print(f"Max retries reached for {paper['arXiv_id']}, skipping.")
                    result = {
                        "title": paper["title"],
                        "chinese_title": paper["title"],
                        "english_title": paper["title"],
                        "arXiv_id": paper["arXiv_id"],
                        "abstract": paper["abstract"],
                        "authors": "未知",
                        "contribution": "总结失败",
                        "method_summary": "",
                        "relevance_reason": "",
                        "summary": "总结失败",
                        "relevance_score": 0,
                        "priority": "Low",
                        "pdf_url": paper.get("pdf_url", ""),
                        "abstract_url": paper.get("abstract_url", ""),
                    }
                    if cache_path:
                        try:
                            with self.lock:
                                with open(cache_path, "w", encoding="utf-8") as cache_file:
                                    json.dump(result, cache_file, ensure_ascii=False, indent=2)
                        except OSError:
                            pass
                    return result
                time.sleep(1)

    def get_recommendation(self):
        recommendations = {}
        for category, papers in self.papers.items():
            for paper in papers:
                recommendations[paper["arXiv_id"]] = paper

        print(
            f"Got {len(recommendations)} non-overlapping papers from yesterday's arXiv."
        )

        recommendations_ = []
        print("Performing LLM inference...")

        with ThreadPoolExecutor(self.num_workers) as executor:
            futures = []
            for arXiv_id, paper in recommendations.items():
                futures.append(executor.submit(self.process_paper, paper))
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Processing papers",
                unit="paper",
            ):
                result = future.result()
                if result:
                    recommendations_.append(result)

        recommendations_ = sorted(
            recommendations_, key=lambda x: x["relevance_score"], reverse=True
       )[: self.max_paper_num]

        # Save pushed IDs to history
        for r in recommendations_:
            self.pushed_ids.add(r["arXiv_id"])
        self._save_history()

        # Save recommendation to markdown file
        if self.save_dir:
            current_time = self.run_datetime
            save_path = os.path.join(
                self.save_dir, self.run_date, f"{current_time.strftime('%Y-%m-%d')}.md"
            )
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("# Daily arXiv Papers\n")
                f.write(f"## Date: {current_time.strftime('%Y-%m-%d')}\n")
                f.write(f"## Papers:\n")
                for i, paper in enumerate(recommendations_):
                    f.write(f"### {i + 1}. {paper.get('chinese_title', paper['title'])}\n")
                    f.write(f"- English: {paper.get('english_title', paper['title'])}\n")
                    f.write(f"- Authors: {paper.get('authors', '未知')}\n")
                    f.write(f"- Contribution: {paper.get('contribution', '')}\n")
                    f.write(f"- Method: {paper.get('method_summary', '')}\n")
                    f.write(f"- Relevance: {paper['relevance_score']}/10 ({paper.get('priority', 'Medium')})\n")
                    f.write(f"- Why: {paper.get('relevance_reason', '')}\n")
                    f.write(f"- PDF: {paper['pdf_url']}\n\n")

        return recommendations_

    def summarize(self, recommendations):
        overview = ""
        for i in range(len(recommendations)):
            p = recommendations[i]
            overview += f"{i + 1}. {p['title']} - {p.get('contribution', p.get('summary', ''))} (Score: {p['relevance_score']})\n"

        prompt = f"""
你是一个有帮助的学术研究助手，可以帮助我构建每日论文推荐系统。
以下是我最近研究领域的描述：
{self.description}

以下是我从昨天的 arXiv 爬取的论文，我为你提供了标题和贡献总结：
{overview}

请务必严格按照以下 JSON 结构返回内容，不要添加额外文本或代码块：
{{
  "overview": {{
    "total_scanned": <今日扫描论文总数>,
    "total_selected": <入选论文数量>,
    "top3": [
      {{"title": "<论文标题>", "reason": "<推荐理由>"}}
    ],
    "trend_summary": "<今日主题趋势总结，用中文>"
  }}
}}

任务要求：
1. 统计今日扫描和入选论文数量。
2. 从入选论文中精选 Top 3 最值得阅读的论文，说明推荐理由。
3. 总结今日论文体现的整体研究趋势，解释其与我研究兴趣的联系。
"""

        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                raw_response = self.model.inference(
                    prompt, temperature=self.temperature
                )
                cleaned = raw_response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                    if "\n" in cleaned:
                        first_line, rest = cleaned.split("\n", 1)
                        if first_line.strip().lower() in ("json", "html"):
                            cleaned = rest
                        else:
                            cleaned = first_line + "\n" + rest
                cleaned = cleaned.strip()
                if "{" in cleaned:
                    cleaned = cleaned[cleaned.index("{"):]
                if "}" in cleaned:
                    cleaned = cleaned[:cleaned.rindex("}") + 1]
                data = json.loads(cleaned)
                overview_data = data.get("overview", data)
                return render_overview_html(
                    overview_data.get("total_scanned", self.total_fetched),
                    overview_data.get("total_selected", len(recommendations)),
                    overview_data.get("top3", []),
                    overview_data.get("trend_summary", "暂无趋势信息"),
                )
            except Exception as error:
                print(f"Overview generation attempt {attempt} failed: {error}")
                if attempt == max_retries:
                    return render_overview_html(
                        self.total_fetched,
                        len(recommendations),
                        [],
                        "趋势总结生成失败，请查看下方论文列表。",
                    )

    def render_email(self, recommendations):
        if self.save_dir:
            save_file_path = os.path.join(self.save_dir, self.run_date, "arxiv_daily_email.html")
            if os.path.exists(save_file_path):
                with open(save_file_path, "r", encoding="utf-8") as f:
                    print(f"Email loaded from cache: {save_file_path}")
                    return f.read()

        parts = []
        if len(recommendations) == 0:
            return framework.replace("__CONTENT__", get_empty_html())

        for i, p in enumerate(tqdm(recommendations, desc="Rendering Emails")):
            rate = get_stars(p["relevance_score"])
            parts.append(
                get_block_html(
                    index=i + 1,
                    chinese_title=p.get("chinese_title", p["title"]),
                    english_title=p.get("english_title", p["title"]),
                    rate=rate,
                    arxiv_id=p["arXiv_id"],
                    authors=p.get("authors", "未知"),
                    contribution=p.get("contribution", ""),
                    method_summary=p.get("method_summary", ""),
                    relevance_reason=p.get("relevance_reason", ""),
                    relevance_score=p["relevance_score"],
                    priority=p.get("priority", "Medium"),
                    pdf_url=p["pdf_url"],
                )
            )

        overview = self.summarize(recommendations)
        content = overview + "<br>" + "</br><br>".join(parts) + "</br>"
        email_html = framework.replace("__CONTENT__", content)

        # Save rendered email
        if self.save_dir:
            save_path = os.path.join(self.save_dir, self.run_date, "arxiv_daily_email.html")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(email_html)

        return email_html

    def send_email(
        self,
        sender: str,
        receiver: str,
        password: str,
        smtp_server: str,
        smtp_port: int,
        title: str,
    ):
        recommendations = self.get_recommendation()
        html = self.render_email(recommendations)

        def _format_addr(s):
            name, addr = parseaddr(s)
            return formataddr((Header(name, "utf-8").encode(), addr))

        msg = MIMEText(html, "html", "utf-8")
        msg["From"] = _format_addr(f"{title} <%s>" % sender)

        receivers = [addr.strip() for addr in receiver.split(",")]
        msg["To"] = ",".join([_format_addr(f"You <%s>" % addr) for addr in receivers])

        today = self.run_datetime.strftime("%Y/%m/%d")
        msg["Subject"] = Header(f"{title} {today}", "utf-8").encode()

        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        except Exception as e:
            print(f"TLS failed: {e}, trying SSL.")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)

        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())
        server.quit()
        print("Email sent successfully!")


if __name__ == "__main__":
    categories = ["cs.AI", "cs.CL", "cs.LG", "cs.IR"]
    max_entries = 100
    max_paper_num = 50
    provider = "openai"
    model = "glm-4.5-air"
    description = """
        I am working on the research area of computer vision and natural language processing.
        Specifically, I am interested in the following fields:
        1. Object detection
        2. AIGC (AI Generated Content)
        3. Multimodal Large Language Models

        I'm not interested in the following fields:
        1. 3D Vision
        2. Robotics
        3. Low-level Vision
    """

    arxiv_daily = ArxivDaily(
        categories, max_entries, max_paper_num, provider, model,
        "https://open.bigmodel.cn/api/coding/paas/v4", "your-api-key", description,
        4, 0.3, "./arxiv_history"
    )
    recommendations = arxiv_daily.get_recommendation()
    print(recommendations)
