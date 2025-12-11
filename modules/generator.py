import os
import json
import re
import textwrap
from datetime import datetime
from utils.logger import logger

# Optional OpenAI client
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# Initialize OpenAI client
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in environment. Please configure your .env file.")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a concise computer science teacher. "
    "Generate slide content for an Instagram carousel. "
    "Output must be valid JSON in this exact structure:\n"
    "{\"slides\": [{\"heading\": \"...\", \"body\": \"...\"}, {...}]}\n"
    "Rules:\n"
    "1. Return EXACTLY 2 slides.\n"
    "2. Slide 1: What/Why/When + Syntax (with small python code snippet in markdown)small mention of time complexity and space complexity as tc and sc in one line.\n"
    "3. Slide 2: top interview questions and problems to solve of 6 and give small analogy about topic in last point.\n"
    "4. Output ONLY valid JSON — no text outside JSON."
)

def _extract_json(text: str):
    """Safely extract JSON block, even if wrapped in formatting."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'({[\s\S]*})', text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    raise ValueError("Response could not be parsed as JSON.")

def generate_topic_slides(topic_name: str):
    """
    Generates slide content for the given topic using GPT-4o-mini.
    Always returns exactly 2 slides as JSON.
    """
    topic = (topic_name or "Topic").strip()
    logger.info("Generating slides for topic: %s", topic)

    user_prompt = (
        f"Create EXACTLY 2 slides for Instagram about: {topic}. "
        "Slide 1: What & Why & When + Syntax (python snippet included) small mention "
        "of time complexity and space complexity as tc and sc in one line. "
        "Slide 2: Important Interview Questions and problems to solve "
        "(6 concise bullet points) with small analogy. "
        "Output ONLY valid JSON according to structure "
        "{\"slides\":[{\"heading\":\"\",\"body\":\"\"},{\"heading\":\"\",\"body\":\"\"}]}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=700,
        )

        text = response.choices[0].message.content.strip()
        parsed = _extract_json(text)
        slides = parsed.get("slides", [])

        if not isinstance(slides, list) or len(slides) != 2:
            raise ValueError(f"Unexpected slide structure: {slides}")

        clean_slides = []
        for s in slides:
            heading = s.get("heading", "").strip()
            body = textwrap.dedent(s.get("body", "").strip())
            if not heading or not body:
                raise ValueError(f"Incomplete slide: {s}")
            clean_slides.append({"heading": heading, "body": body})

        logger.info("✅ Successfully generated slides for topic: %s", topic)
        return clean_slides

    except Exception as e:
        logger.exception("❌ Error generating slides for topic '%s': %s", topic, e)
        raise RuntimeError(f"Failed to generate slides for '{topic}' due to: {e}")


# ---------------------------------------------------------------------------
# NEW FEATURES: Quiz and Guess Output Generators
# ---------------------------------------------------------------------------

def generate_quiz_slides(topic_name: str):
    """Generate 5-slide Weekly Quiz Challenge for Instagram."""
    topic = (topic_name or "Python Quiz").strip()
    logger.info("Generating Quiz slides for topic: %s", topic)

    # CUSTOM SYSTEM PROMPT for quiz (overrides the 2-slide restriction)
    quiz_system_prompt = (
        "You are an expert computer science teacher creating Instagram quiz content. "
        "Generate EXACTLY 5 slides in valid JSON format: "
        "{\"slides\": [{\"heading\": \"...\", \"body\": \"...\"}, ...]} "
        "Output ONLY valid JSON — no extra text."
    )

    user_prompt = (
        f"Create a 5-slide 'Weekly Quiz Challenge' about {topic}.\n\n"
        "Slide 1: Question 1 with 4 multiple-choice options (A, B, C, D). Only one is correct.\n"
        "Slide 2: Question 2 with 4 multiple-choice options (A, B, C, D). Only one is correct.\n"
        "Slide 3: Question 3 with 4 multiple-choice options (A, B, C, D). Only one is correct.\n"
        "Slide 4: Question 4 with 4 multiple-choice options (A, B, C, D). Only one is correct.\n"
        "Slide 5: Title 'Answers & Explanations'. Show all 4 correct answers (Q1: A, Q2: C, etc.) "
        "with a short 1-line explanation for each. End with 'Comment your score below '.\n\n"
        "Each question slide should have:\n"
        "- heading: 'Question X'\n"
        "- body: the question text followed by options A, B, C, D on separate lines.\n\n"
        "Return valid JSON with exactly 5 slides."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": quiz_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=1200,
        )
        text = response.choices[0].message.content.strip()
        parsed = _extract_json(text)
        slides = parsed.get("slides", [])

        clean = []
        for s in slides:
            heading = s.get("heading", "").strip()
            body = textwrap.dedent(s.get("body", "").strip())
            if heading and body:
                clean.append({"heading": heading, "body": body})

        logger.info("✅ Successfully generated %d quiz slides for: %s", len(clean), topic)
        return clean

    except Exception as e:
        logger.exception("❌ Error generating quiz slides for '%s': %s", topic, e)
        raise RuntimeError(f"Failed to generate quiz slides for '{topic}' due to: {e}")
    
def generate_logic_puzzle_slides(topic_name: str):
    """Generate 2-slide carousel for Logic & Puzzle topics with structured explanations."""
    topic = (topic_name or "Logic Puzzle").strip()
    logger.info("Generating Logic & Puzzle slides for: %s", topic)

    # More specific system prompt
    system_prompt = (
    "You are a professional logic and reasoning teacher who creates clean, simple, step-by-step educational Instagram carousels. "
    "Your goal is to explain logic puzzles clearly and visually — each rule or step must appear on a separate line for better readability.\n\n"
    "You must generate EXACTLY 2 slides in valid JSON format.\n\n"
    "STRUCTURE:\n"
    "Slide 1: Puzzle Question & Rules\n"
    "- Heading: A short, creative title for the puzzle (e.g., 'The River Crossing Puzzle').\n"
    "- Body: Start with the line ' Puzzle Question:' followed by 1–3 short lines explaining the puzzle.\n"
    "  Then, clearly list each rule or condition in a new line using numbers or bullet points.\n"
    "  Keep language simple and clear — one idea per line.\n\n"
    "Slide 2: Step-by-Step Solution\n"
    "- Heading: 'Solution & Key Takeaway'\n"
    "- Body: Start with the line ' Step-by-Step Solution:' followed by each reasoning step on a new line.\n"
    "  Each step must be numbered clearly (1, 2, 3...).\n"
    "  At the end, include a line starting with ' Key Point to Remember:' that gives one short takeaway or lesson from the puzzle.\n\n"
    "REQUIREMENTS:\n"
    "- The 'body' field must be a single STRING (not a list or dict).\n"
    "- Each rule or step must appear on a new line using '\\n'.\n"
    "- Output MUST be valid JSON only — no markdown, no code fences, no explanations.\n\n"
    "OUTPUT FORMAT:\n"
    "{\"slides\": [\n"
    "  {\"heading\": \"...\", \"body\": \"...\"},\n"
    "  {\"heading\": \"...\", \"body\": \"...\"}\n"
    "]}"
)


    user_prompt = (
    f"Create a 2-slide Instagram carousel about the logic puzzle: {topic_name.strip()}.\n\n"
    "Follow this exact structure:\n\n"
    "Slide 1 - Puzzle Question & Rules:\n"
    "- Heading: The name/title of the puzzle.\n"
    "- Body: Begin with ' Puzzle Question:' and explain the puzzle clearly in 2–3 short lines.\n"
    "  Then list each rule or constraint on a separate line, numbered (1., 2., 3., etc.).\n"
    "  Use simple, clear English so anyone can understand.\n\n"
    "Slide 2 - Step-by-Step Solution:\n"
    "- Heading: 'Solution & Key Takeaway'\n"
    "- Body: Begin with ' Step-by-Step Solution:' and write each reasoning step in a new line, numbered clearly.\n"
    "  After listing the steps, write one final line starting with ' Key Point to Remember:' to summarize the main logic or concept learned from the puzzle.\n\n"
    "Make sure each line appears separately using '\\n'.\n"
    "Return ONLY the JSON with exactly 2 slides as described above."
    )


    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1000,
        )

        text = response.choices[0].message.content.strip()
        logger.info("Raw API response: %s", text)
        
        # Try multiple parsing strategies
        parsed = None
        clean_slides = []
        
        # Strategy 1: Direct JSON parsing
        try:
            parsed = json.loads(text)
            slides = parsed.get("slides", [])
            if slides:
                for s in slides[:2]:  # Take first 2 slides only
                    if isinstance(s, dict):
                        heading = s.get("heading", "").strip()
                        body_raw = s.get("body", "")
                        
                        # Handle body whether it's string or dict
                        if isinstance(body_raw, dict):
                            # Convert dict to string format
                            body_parts = []
                            for key, value in body_raw.items():
                                body_parts.append(f"**{key}:**\n{value}")
                            body = "\n\n".join(body_parts)
                        elif isinstance(body_raw, str):
                            body = body_raw.strip()
                        else:
                            body = str(body_raw)
                        
                        if heading and body:
                            clean_slides.append({"heading": heading, "body": body})
        except Exception as e:
            logger.warning("Strategy 1 failed: %s", e)
        
        # Strategy 2: Look for alternative structures
        if not clean_slides and parsed:
            for key in ["slide1", "slide_1", "first_slide", "slide_one"]:
                if key in parsed:
                    slide_data = parsed[key]
                    if isinstance(slide_data, dict):
                        heading = slide_data.get("heading", slide_data.get("title", f"{topic} - Problem"))
                        body_raw = slide_data.get("body", slide_data.get("content", ""))
                        
                        if isinstance(body_raw, dict):
                            body = "\n".join([f"{k}: {v}" for k, v in body_raw.items()])
                        else:
                            body = str(body_raw)
                            
                        clean_slides.append({"heading": str(heading), "body": body})
                        break
            
            for key in ["slide2", "slide_2", "second_slide", "slide_two"]:
                if key in parsed:
                    slide_data = parsed[key]
                    if isinstance(slide_data, dict):
                        heading = slide_data.get("heading", slide_data.get("title", f"{topic} - Hints"))
                        body_raw = slide_data.get("body", slide_data.get("content", ""))
                        
                        if isinstance(body_raw, dict):
                            body = "\n".join([f"{k}: {v}" for k, v in body_raw.items()])
                        else:
                            body = str(body_raw)
                            
                        clean_slides.append({"heading": str(heading), "body": body})
                        break
        
        # Strategy 3: Create fallback content if still no slides
        if len(clean_slides) < 2:
            logger.warning("API response didn't contain valid slides, creating fallback content")
            
            # Clear any partial slides and create complete fallback
            clean_slides = []
            
            # Truncate topic name for readability
            short_topic = topic[:30] + "..." if len(topic) > 30 else topic
            
            fallback_slides = [
                {
                    "heading": f"{short_topic} - Logic Puzzle",
                    "body": f"🔍 **Problem Statement:**\nA fascinating {short_topic} that challenges your logical thinking!\n\n📋 **Rules & Constraints:**\n• Analyze the given conditions carefully\n• Consider all possibilities systematically\n• Look for patterns and relationships\n\n💡 **Solution Approach:**\n1. Break down the problem into smaller parts\n2. Test different scenarios methodically\n3. Eliminate impossible cases\n4. Verify your solution meets all constraints"
                },
                {
                    "heading": f"{short_topic} - Hints & Solution",
                    "body": "🧠 **6 Key Problem-Solving Hints:**\n• Work backwards from the desired outcome\n• Consider edge cases and boundaries\n• Look for symmetry or patterns\n• Use process of elimination\n• Simplify complex relationships\n• Test your assumptions systematically\n\n🌟 **Memory Tip:** Think of this like solving a mystery - gather clues, eliminate suspects, and verify your conclusion fits all the evidence!"
                }
            ]
            
            clean_slides = fallback_slides

        # Ensure we have exactly 2 slides
        while len(clean_slides) < 2:
            short_topic = topic[:30] + "..." if len(topic) > 30 else topic
            clean_slides.append({
                "heading": f"{short_topic} - Part {len(clean_slides) + 1}",
                "body": f"Additional insights about the {short_topic} logic puzzle."
            })
        
        if len(clean_slides) > 2:
            clean_slides = clean_slides[:2]

        logger.info("✅ Generated %d structured Logic & Puzzle slides for: %s", len(clean_slides), topic)
        return clean_slides

    except Exception as e:
        logger.exception("❌ Failed structured Logic & Puzzle slide generation for '%s': %s", topic, e)
        
        # Comprehensive fallback with truncated topic name
        short_topic = topic[:30] + "..." if len(topic) > 30 else topic
        
        return [
            {
                "heading": f"{short_topic} - Logic Challenge",
                "body": f"🧩 **The {short_topic} Puzzle**\n\nA classic logic problem that tests your analytical skills and attention to detail. Perfect for sharpening your problem-solving abilities!\n\n🔍 **Key Aspects:**\n• Systematic thinking\n• Pattern recognition\n• Constraint analysis\n• Logical deduction"
            },
            {
                "heading": f"{short_topic} - Solving Strategy",
                "body": "💡 **6 Essential Hints:**\n1. Start with what you know for certain\n2. Map out all possibilities\n3. Look for contradictions\n4. Work step by step\n5. Double-check your reasoning\n6. Consider alternative perspectives\n\n🎯 **Pro Tip:** Great logic puzzles teach you to question assumptions and think systematically - skills that apply to programming and real-world problem solving!"
            }
        ]




def generate_guess_output_slides(topic_name: str):
    """
    Generate 3-slide 'Guess the Output' interactive carousel with improved prompt logic.
    Ensures code is logically correct and demonstrates the actual algorithm/concept properly.
    """
    topic = (topic_name or "Python Output").strip()
    logger.info("Generating 'Guess the Output' slides for topic: %s", topic)

    # Enhanced system prompt emphasizing correctness and educational value
    guess_system_prompt = (
        "You are an expert Python educator creating Instagram 'Guess the Output' content. "
        "Your goal is to help learners understand real Python behavior through working code examples. "
        "CRITICAL: All code MUST be syntactically correct, logically sound, and actually executable. "
        "Generate EXACTLY 3 slides in valid JSON format: "
        "{\"slides\": [{\"heading\": \"...\", \"body\": \"...\"}, ...]} "
        "Do NOT include any text outside JSON. Keep all code in markdown blocks (```)."
        "Ensure the code demonstrates the core concept accurately and will produce meaningful output."
    )

    user_prompt = (
    f"Create a 3-slide 'Guess the Output' carousel about: {topic}\n\n"
    f"IMPORTANT: The code snippet MUST be a CORRECT, WORKING implementation that properly demonstrates {topic}. "
    "Use a realistic, executable example (5-12 lines) that highlights the key concept or behavior.\n\n"
    
    "Slide 1 - The Challenge:\n"
    "- heading: 'Guess the Output '\n"
    "- body: Include a complete, working Python code snippet in a markdown code block (```)."
    "DO NOT include any comment lines that mention the topic name or algorithm name at the start. "
    "Start directly with the actual executable code. "
    "The code should be interesting and thought-provoking but CORRECT. "
    "End with: 'What will be the output? Comment your guess below! '\n\n"
    
    "Slide 2 - The Hint:\n"
    "- heading: 'Hint '\n"
    "- body: Provide ONE clear, concise hint (1-2 sentences) about how the code executes or what Python behavior to consider. "
    "Focus on the key concept (e.g., mutability, scope, evaluation order, data structure behavior).\n\n"
    
    "Slide 3 - The Answer:\n"
    "- heading: 'Answer '\n"
    "- body: First, clearly state the exact output in a code block or formatted text. "
    "Then provide a 2-3 sentence explanation of WHY that output occurs, connecting it to the Python concept being demonstrated "
    f"(related to {topic}).\n\n"
    
    "Requirements:\n"
    "- Code must be syntactically correct and executable\n"
    "- Code should produce actual, meaningful output\n"
    "- DO NOT include topic name or algorithm name as a comment in the code\n"
    "- Explanation must be accurate and educational\n"
    "- Return valid JSON with exactly 3 slides: "
    "{\"slides\":[{\"heading\":\"\",\"body\":\"\"},{\"heading\":\"\",\"body\":\"\"},{\"heading\":\"\",\"body\":\"\"}]}"
)

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": guess_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for more consistent, accurate code
            max_tokens=1000,  # Increased for complete explanations
        )

        # Correctly access the response
        text = response.choices[0].message.content.strip()
        parsed = _extract_json(text)
        slides = parsed.get("slides", [])

        # Validate we have exactly 3 slides
        if len(slides) != 3:
            logger.warning("Expected 3 slides but got %d. Retrying may be needed.", len(slides))

        final_slides = []
        for s in slides:
            heading = s.get("heading", "").strip()
            body = textwrap.dedent(s.get("body", "").strip())
            if heading and body:
                final_slides.append({"heading": heading, "body": body})

        if len(final_slides) < 3:
            logger.warning("Only %d valid slides generated for topic: %s", len(final_slides), topic)

        logger.info("✅ Successfully generated %d 'Guess the Output' slides for: %s", len(final_slides), topic)
        return final_slides

    except Exception as e:
        logger.exception("❌ Error generating 'Guess the Output' slides for '%s': %s", topic, e)
        raise RuntimeError(f"Failed to generate Guess Output slides for '{topic}' due to: {e}")
    
    

