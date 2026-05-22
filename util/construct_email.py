import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
from datetime import datetime, timezone
from loguru import logger

framework = """
<!DOCTYPE HTML>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
    .star-wrapper {
      font-size: 1.3em;
      line-height: 1;
      display: inline-flex;
      align-items: center;
    }
    .half-star {
      display: inline-block;
      width: 0.5em;
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
    .paper-block {
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 20px;
      background-color: #ffffff;
      margin-bottom: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .paper-title-cn {
      font-size: 18px;
      font-weight: 700;
      color: #1a1a1a;
      margin: 0 0 4px 0;
    }
    .paper-title-en {
      font-size: 14px;
      color: #6b7280;
      margin: 0 0 12px 0;
      font-style: italic;
    }
    .paper-meta {
      font-size: 13px;
      color: #6b7280;
      margin-bottom: 12px;
    }
    .paper-field {
      margin: 6px 0;
      font-size: 14px;
      line-height: 1.6;
    }
    .paper-field strong {
      color: #374151;
    }
    .score-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
    }
    .score-high { background: #dcfce7; color: #166534; }
    .score-medium { background: #fef3c7; color: #92400e; }
    .score-low { background: #fee2e2; color: #991b1b; }
    .priority-high { background: #dbeafe; color: #1e40af; }
    .priority-medium { background: #fef3c7; color: #92400e; }
    .priority-low { background: #f3f4f6; color: #6b7280; }
    .arxiv-link {
      display: inline-block;
      text-decoration: none;
      font-size: 13px;
      color: #2563eb;
    }
    .pdf-btn {
      display: inline-block;
      text-decoration: none;
      font-size: 13px;
      font-weight: bold;
      color: #fff;
      background-color: #dc2626;
      padding: 6px 14px;
      border-radius: 4px;
    }
    .overview-section {
      border-radius: 16px;
      padding: 24px 28px;
      background: linear-gradient(135deg, rgba(66,133,244,0.12), rgba(219,68,55,0.08));
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
      margin-bottom: 32px;
    }
    .overview-section h2 {
      margin: 0 0 12px 0;
      font-size: 20px;
      color: #1f2937;
      border-bottom: 2px solid rgba(59,130,246,0.2);
      padding-bottom: 8px;
    }
    .overview-section p {
      margin: 4px 0;
      line-height: 1.7;
      color: #374151;
      font-size: 14px;
    }
    .overview-stats {
      display: flex;
      gap: 24px;
      margin: 12px 0;
    }
    .overview-stat {
      text-align: center;
    }
    .overview-stat-num {
      font-size: 28px;
      font-weight: 700;
      color: #2563eb;
    }
    .overview-stat-label {
      font-size: 12px;
      color: #6b7280;
    }
    .top3-item {
      padding: 8px 0;
      border-bottom: 1px solid rgba(0,0,0,0.05);
    }
    .top3-item:last-child {
      border-bottom: none;
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div style="font-size: 12px; color: #999;">
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""


def get_empty_html():
    return """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  """


def render_overview_html(total_scanned, total_selected, top3, trend_summary):
    """Render the daily overview section at the top of the email."""
    top3_html = ""
    if top3:
        for i, item in enumerate(top3):
            title = item.get("title", "")
            reason = item.get("reason", "")
            top3_html += f'<div class="top3-item"><strong>Top {i+1}:</strong> {title}<br><span style="color:#6b7280;font-size:13px;">{reason}</span></div>'
    else:
        top3_html = "<p>暂无 Top 3 推荐。</p>"

    return f"""
<div class="overview-section">
  <h2>Daily Overview</h2>
  <div class="overview-stats">
    <div class="overview-stat">
      <div class="overview-stat-num">{total_scanned}</div>
      <div class="overview-stat-label">Scanned</div>
    </div>
    <div class="overview-stat">
      <div class="overview-stat-num">{total_selected}</div>
      <div class="overview-stat-label">Selected</div>
    </div>
  </div>
  <h2>Top 3 Recommendations</h2>
  {top3_html}
  <h2>Trend Summary</h2>
  <p>{trend_summary}</p>
</div>
"""


def get_block_html(
    index,
    chinese_title,
    english_title,
    rate,
    arxiv_id,
    authors,
    contribution,
    method_summary,
    relevance_reason,
    relevance_score,
    priority,
    pdf_url,
):
    # Score badge color
    if relevance_score >= 7:
        score_class = "score-high"
    elif relevance_score >= 4:
        score_class = "score-medium"
    else:
        score_class = "score-low"

    # Priority badge
    priority_lower = priority.lower() if priority else "medium"
    if priority_lower == "high":
        priority_class = "priority-high"
    elif priority_lower == "medium":
        priority_class = "priority-medium"
    else:
        priority_class = "priority-low"

    arxiv_link = f"https://arxiv.org/abs/{arxiv_id}"

    return f"""
<div class="paper-block">
  <div class="paper-title-cn">{index}. {chinese_title}</div>
  <div class="paper-title-en">{english_title}</div>
  <div class="paper-meta">
    <strong>Authors:</strong> {authors} &nbsp;|&nbsp;
    <strong>arXiv:</strong> <a class="arxiv-link" href="{arxiv_link}">{arxiv_id}</a> &nbsp;|&nbsp;
    <span class="score-badge {score_class}">Score: {relevance_score}/10</span>
    <span class="score-badge {priority_class}">{priority}</span>
    {rate}
  </div>
  <div class="paper-field"><strong>Core Contribution:</strong> {contribution}</div>
  <div class="paper-field"><strong>Method:</strong> {method_summary}</div>
  <div class="paper-field"><strong>Why Relevant:</strong> {relevance_reason}</div>
  <div style="margin-top: 10px;">
    <a class="pdf-btn" href="{pdf_url}">PDF</a>
  </div>
</div>
"""


def get_stars(score: float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 2
    high = 8
    if score <= low:
        return ""
    elif score >= high:
        return full_star * 5
    else:
        interval = (high - low) / 10
        star_num = math.ceil((score - low) / interval)
        full_star_num = int(star_num / 2)
        half_star_num = star_num - full_star_num * 2
        return (
            '<div class="star-wrapper">'
            + full_star * full_star_num
            + half_star * half_star_num
            + "</div>"
        )


def send_email(
    sender: str,
    receiver: str,
    password: str,
    smtp_server: str,
    smtp_port: int,
    html: str,
):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, "utf-8").encode(), addr))

    msg = MIMEText(html, "html", "utf-8")
    msg["From"] = _format_addr("Github Action <%s>" % sender)
    msg["To"] = _format_addr("You <%s>" % receiver)
    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    msg["Subject"] = Header(f"Daily arXiv {today}", "utf-8").encode()

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
    except Exception as e:
        logger.warning(f"Failed to use TLS. {e}")
        logger.warning(f"Try to use SSL.")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)

    server.login(sender, password)
    server.sendmail(sender, [receiver], msg.as_string())
    server.quit()
