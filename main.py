from util.construct_email import send_email
from arxiv_daily import ArxivDaily
import argparse
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arxiv Daily")
    parser.add_argument(
        "--categories",
        nargs="+",
        help="arXiv categories",
        default=["cs.AI", "cs.CL", "cs.LG", "cs.IR"],
    )
    parser.add_argument("--max_paper_num", type=int, help="max_paper_num", default=60)
    parser.add_argument(
        "--max_entries", type=int, help="max_entries to get from arxiv", default=100
    )
    parser.add_argument(
        "--provider", type=str, help="provider", default="OpenAI"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="model name (env: GLM_MODEL)",
        default=os.environ.get("GLM_MODEL", "glm-4.5-air"),
    )
    parser.add_argument(
        "--save", action="store_true", help="Save the email content to a file."
    )
    parser.add_argument("--save_dir", type=str, default="./arxiv_history")

    parser.add_argument(
        "--base_url",
        type=str,
        help="base_url",
        default="https://open.bigmodel.cn/api/paas/v4/",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        help="API key (env: GLM_API_KEY)",
        default=os.environ.get("GLM_API_KEY"),
    )

    parser.add_argument(
        "--description",
        type=str,
        help="Path to the file that describes your interested research area.",
        default="description.txt",
    )

    parser.add_argument(
        "--smtp_server",
        type=str,
        help="SMTP server (env: SMTP_SERVER)",
        default=os.environ.get("SMTP_SERVER"),
    )
    parser.add_argument(
        "--smtp_port",
        type=int,
        help="SMTP port (env: SMTP_PORT)",
        default=int(os.environ.get("SMTP_PORT", "465")),
    )
    parser.add_argument(
        "--sender",
        type=str,
        help="Sender email (env: SMTP_SENDER)",
        default=os.environ.get("SMTP_SENDER"),
    )
    parser.add_argument(
        "--receiver",
        type=str,
        help="Receiver email (env: SMTP_RECEIVER)",
        default=os.environ.get("SMTP_RECEIVER"),
    )
    parser.add_argument(
        "--sender_password",
        type=str,
        help="Sender email password (env: SMTP_PASSWORD)",
        default=os.environ.get("SMTP_PASSWORD"),
    )
    parser.add_argument("--temperature", type=float, help="Temperature", default=0.3)

    parser.add_argument("--num_workers", type=int, help="Number of workers", default=4)
    parser.add_argument(
        "--title", type=str, help="Title of the email", default="Daily arXiv"
    )

    args = parser.parse_args()

    # Validate required settings
    if not (args.provider == "Ollama" or args.provider == "ollama"):
        assert args.api_key is not None, (
            "api_key is required. Set GLM_API_KEY env var or pass --api_key."
        )

    assert args.smtp_server is not None, (
        "SMTP server is required. Set SMTP_SERVER env var or pass --smtp_server."
    )
    assert args.sender is not None, (
        "Sender email is required. Set SMTP_SENDER env var or pass --sender."
    )
    assert args.receiver is not None, (
        "Receiver email is required. Set SMTP_RECEIVER env var or pass --receiver."
    )
    assert args.sender_password is not None, (
        "Sender password is required. Set SMTP_PASSWORD env var or pass --sender_password."
    )

    with open(args.description, "r", encoding="utf-8") as f:
        args.description = f.read()

    # Test LLM availability
    if args.provider == "Ollama" or args.provider == "ollama":
        from llm.Ollama import Ollama

        try:
            model = Ollama(args.model)
            model.inference("Hello, who are you?")
        except Exception as e:
            print(e)
            assert False, "Model not initialized successfully."
    elif (
        args.provider == "OpenAI"
        or args.provider == "openai"
        or args.provider == "SiliconFlow"
        or args.provider == "siliconflow"
    ):
        from llm.GPT import GPT

        try:
            model = GPT(args.model, args.base_url, args.api_key)
            model.inference("Hello, who are you?")
        except Exception as e:
            print(e)
            assert False, "Model not initialized successfully."
    else:
        assert False, "Model not supported."

    if args.save:
        os.makedirs(args.save_dir, exist_ok=True)
    else:
        args.save_dir = None

    arxiv_daily = ArxivDaily(
        args.categories,
        args.max_entries,
        args.max_paper_num,
        args.provider,
        args.model,
        args.base_url,
        args.api_key,
        args.description,
        args.num_workers,
        args.temperature,
        args.save_dir,
    )

    arxiv_daily.send_email(
        args.sender,
        args.receiver,
        args.sender_password,
        args.smtp_server,
        args.smtp_port,
        args.title,
    )
