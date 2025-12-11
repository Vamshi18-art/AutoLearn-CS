🚀 AutoLearn CS – AI-Driven CS Learning & Content Automation System

AutoLearn CS is an AI-powered autonomous system that automates computer science learning by extracting topics from the web, generating summaries & quizzes with LLMs, and creating Instagram-ready educational posts.
The system integrates Playwright, LangChain, and Instagram Business API to deliver end-to-end automation with 90% reduction in manual effort.

🌟 Features
🔍 1. Automated CS Topic Extraction (Playwright)

Scrapes concepts, problems, explanations from learning platforms.

Handles dynamic websites with retry + wait strategies.

🧠 2. AI Summaries & Quiz Generation (LangChain + LLMs)

Generates clean summaries, explanations, and quiz questions.

Avoids hallucinations using structured prompts & output parsers.

🎨 3. Auto-Generated Instagram Carousel Posts

Converts extracted content into visually appealing 1080×1080 slides.

Uses custom templates built with Pillow.

📤 4. Instagram Business API Integration

Automatically uploads carousel posts and captions.

Supports instant publishing & scheduled posting.

🔄 5. Fully Autonomous Workflow

Extraction → Processing → AI Generation → Image Creation → Posting
All handled automatically without user intervention.

🛠️ Tech Stack
Languages

Python

AI / LLM

LangChain

OpenAI / LLM APIs

Prompt Engineering

RAG (optional)

Web Automation

Playwright (Browser Automation + Scraping)

Content Generation

Pillow (Image Creation)

Custom Carousel Templates

APIs

Instagram Business Graph API

Facebook Graph API Authentication

Utilities

dotenv

Requests

JSON

Logging System

📁 Project Structure
AutoLearn-CS/
│── data/
│── images/
│── templates/
│── modules/
│   ├── scraper.py
│   ├── ai_pipeline.py
│   ├── post_generator.py
│   ├── instagram_api.py
│   ├── workflow.py
│── ig_session.json (IGNORED)
│── .env (IGNORED)
│── requirements.txt
│── README.md
│── run.py

🧩 System Architecture
[Playwright Scraper]
        ⬇
[AI Processing – LangChain + LLMs]
        ⬇
[Content Formatter + Carousel Generator]
        ⬇
[Instagram API – Auto Publish]

🖥️ Installation & Setup
1️⃣ Clone Repository
git clone https://github.com/Vamshi18-art/AutoLearn-CS.git
cd AutoLearn-CS

2️⃣ Install Dependencies
pip install -r requirements.txt

3️⃣ Setup Environment Variables

Create a .env file:

IG_ACCESS_TOKEN=your_token_here
PAGE_ID=your_page_id
IG_BUSINESS_ID=your_ig_business_id
OPENAI_API_KEY=your_openai_key

4️⃣ Add Instagram Session File

Place your ig_session.json in the root folder.

⚠️ Do NOT upload this file to GitHub.

5️⃣ Run the Automation
python run.py

🧪 Example Output

AI-generated summaries

Quiz questions

Carousel image slides (1080×1080)

Auto-posted Instagram content

💡 Experiences & Challenges Faced
1. Handling Dynamic Websites

Playwright timeouts & selectors failing

Solved with retry logic + stable locators

2. Ensuring AI Output Consistency

LLM hallucinations

Fixed using structured prompts + validators

3. Image Formatting Issues

Text exceeding boundaries

Implemented custom text wrapping & auto-layout

4. Instagram API Errors

Token expiration, upload container failures

Solved using logging + automated retry mechanism

5. Data Flow Automation

Linking scraper → AI → generator → poster

Designed modular pipeline with error recovery

📈 Key Achievements

90% automation of the entire workflow

Real-time AI content generation

Fully autonomous Instagram posting

Demonstrated strong AI + automation + API integration skills

🔐 Security Notes

.env and ig_session.json are ignored for safety

Never commit credentials to GitHub

Uses secure environment variable handling

🤝 Contributing

Pull requests and improvements are welcome!
Feel free to fork and experiment with additional AI features.

📬 Contact

H Vamshi Krishna
📩 Email: vamshikrishna200227@gmail.com

🔗 GitHub: https://github.com/Vamshi18-art
