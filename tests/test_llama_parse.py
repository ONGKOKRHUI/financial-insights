"""
Test LlamaParse API key is working
"""


import asyncio
from llama_cloud import AsyncLlamaCloud
import os
import dotenv

dotenv.load_dotenv()

async def main():
    client = AsyncLlamaCloud(api_key=os.environ.get("LLAMA_CLOUD_API_KEY"))

    # Upload and parse a document
    file_obj = await client.files.create(
        file=r"C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\SUNWAY\SUNWAY_2021_Q1.pdf",
        purpose="parse"
    )

    result = await client.parsing.parse(
        file_id=file_obj.id,
        # The parsing tier. Options: fast, cost_effective, agentic, agentic_plus,
        tier="agentic",

        # The version of the parsing tier to use. Use 'latest' for the most recent version,
        version="latest",

        # 'expand' controls which result fields are returned in the response.,
        # Without it, only job metadata is returned. Common fields:,
        # - "markdown_full", "text_full": Full document content,
        # - "markdown", "text", "items": Page-level content,
        # - "images_content_metadata": Presigned URLs for images,
        expand=["markdown_full", "text_full"],
    )

    # Access the full document content
    print("Full markdown:")
    print(result.markdown_full)

    print("\nFull text:")
    print(result.text_full)

if __name__ == "__main__":
    asyncio.run(main())