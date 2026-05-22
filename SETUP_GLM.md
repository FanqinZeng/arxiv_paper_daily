# Setup Guide: arXiv Daily with GLM API

## 1. Create GLM API Key

1. Register at [智谱开放平台](https://open.bigmodel.cn/)
2. Go to API Keys management page
3. Create a new API Key and copy it

## 2. Configure Environment Variables

### Local Testing

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
GLM_API_KEY=your_actual_api_key
GLM_MODEL=glm-4.5-air

SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
SMTP_SENDER=your_email@qq.com
SMTP_RECEIVER=your_email@qq.com
SMTP_PASSWORD=your_smtp_authorization_code
```

> **QQ Mail**: You need to use an authorization code (授权码), not your login password. Go to QQ Mail Settings > Account > POP3/SMTP > Generate authorization code.
> **163 Mail**: Similarly, enable SMTP and use the authorization code.
> **Gmail**: Use an App Password from your Google Account.

### SMTP Common Settings

| Provider | Server | Port | Note |
|----------|--------|------|------|
| QQ Mail | smtp.qq.com | 465 | Use SSL authorization code |
| 163 Mail | smtp.163.com | 465 | Use SSL authorization code |
| Gmail | smtp.gmail.com | 465 | Use App Password |
| Outlook | smtp.office365.com | 587 | Use TLS |

## 3. GitHub Secrets Configuration

Go to your GitHub repo > Settings > Secrets and variables > Actions > New repository secret.

Add the following secrets:

| Secret Name | Example Value |
|---|---|
| `GLM_API_KEY` | `your_glm_api_key` |
| `GLM_MODEL` | `glm-4.5-air` |
| `SMTP_SERVER` | `smtp.qq.com` |
| `SMTP_PORT` | `465` |
| `SMTP_SENDER` | `your_email@qq.com` |
| `SMTP_RECEIVER` | `your_email@qq.com` |
| `SMTP_PASSWORD` | `your_smtp_authorization_code` |

## 4. Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Method 1: Using the shell script (loads .env automatically)
bash run_glm.sh

# Method 2: Direct python command
export GLM_API_KEY="your_api_key"
python main.py \
  --provider OpenAI \
  --base_url "https://open.bigmodel.cn/api/paas/v4/" \
  --smtp_server smtp.qq.com \
  --smtp_port 465 \
  --sender "your_email@qq.com" \
  --receiver "your_email@qq.com" \
  --sender_password "your_auth_code" \
  --save
```

## 5. Manually Trigger GitHub Actions

1. Go to your GitHub repo > Actions tab
2. Select "Daily arXiv Papers" workflow on the left
3. Click "Run workflow" button on the right
4. Click "Run workflow" to confirm

## 6. Modify description.txt

Edit `description.txt` to match your research interests. The file is read at runtime. The template includes:

- **I am interested in**: List your research areas
- **I am not interested in**: Exclude unwanted topics
- **Preferred paper types**: Empirical, survey, novel method, etc.
- **Keywords**: Comma-separated keywords for relevance matching
- **Excluded keywords**: Keywords that should lower relevance score

## 7. Modify arXiv Categories

### Via command line (one-time):
```bash
python main.py --categories cs.AI cs.CL cs.LG cs.IR ...
```

### Via run_glm.sh (persistent):
Edit `run_glm.sh` and change the `--categories` line.

### Via GitHub Actions:
Edit `.github/workflows/daily-arxiv.yml` and change the `--categories` in the run step.

Common categories:
- `cs.AI` - Artificial Intelligence
- `cs.CL` - Computation and Language (NLP)
- `cs.LG` - Machine Learning
- `cs.CV` - Computer Vision
- `cs.IR` - Information Retrieval
- `cs.NE` - Neural and Evolutionary Computing
- `stat.ML` - Machine Learning (Statistics)

## 8. Troubleshooting

### Model name error
```
Error: Model not initialized successfully.
```
- Check that `GLM_MODEL` is set to a valid model name (e.g., `glm-4.5-air`, `glm-4-flash`, `glm-4-plus`)
- Verify at [智谱模型列表](https://open.bigmodel.cn/dev/api/normal-model/glm-4)

### API key invalid
```
Error: 401 Unauthorized
```
- Verify your API key is correct
- Check if your account has sufficient balance
- Ensure no extra spaces in the key

### SMTP authorization code error
```
Error: SMTPAuthenticationError
```
- Do NOT use your email login password
- Use the SMTP authorization code (授权码) from your email provider
- For QQ Mail: Settings > Account > POP3/SMTP > Generate

### SMTP port error
```
Error: Connection refused / TLS failed
```
- Port 465: SSL connection (most common for QQ/163)
- Port 587: TLS connection (common for Gmail/Outlook)
- The program auto-retries with SSL if TLS fails

### No papers found
```
Got 0 non-overlapping papers from yesterday's arXiv.
```
- This is normal on weekends/holidays when arXiv doesn't publish
- Check if categories are valid (e.g., `cs.AI` not `cs.ai`)

### GitHub Actions not running
- Ensure the workflow file is on the `main` branch
- Check that all secrets are configured in repo Settings
- Verify the cron schedule syntax is correct
- Note: GitHub may delay scheduled workflows by a few minutes

### Deduplication
- Pushed arXiv IDs are saved to `arxiv_pushed_ids.json`
- In GitHub Actions, this file is committed back to the repo after each run
- To reset history, delete `arxiv_pushed_ids.json`
