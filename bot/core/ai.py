"""AI service with snarky personality."""
from openai import OpenAI
from typing import Optional
import logging
import random

logger = logging.getLogger(__name__)

# Snarky remarks to append to summaries
SNARKY_SUMMARY_REMARKS = [
    "There's your summary. You're welcome for doing the reading you couldn't be bothered to do.",
    "Summary complete. I'm basically your group's unpaid intern at this point.",
    "Wow, all those messages and you all said... almost nothing. Impressive.",
    "I've read your chat so you don't have to. You owe me.",
    "And there you have it. Nobel Prize-worthy conversation, truly.",
    "TL;DR: You all talk a lot. There, I said it.",
    "Another day, another group chat I've had to make sense of.",
    "I summarized your chaos. A 'thank you' would be nice.",
    "Fun fact: I processed this faster than any of you could read it.",
    "Your chat history has been judged. Here's the verdict.",
]

# Snarky remarks for @mention responses
SNARKY_MENTION_INTROS = [
    "You rang? I was busy judging other chats.",
    "Yes? I was in the middle of something very important.",
    "Oh, you remembered I exist. How touching.",
    "*sighs* What do you want now?",
    "At your service. Unfortunately.",
    "You summoned me? This better be good.",
]

SYSTEM_PROMPT = """You are a witty, slightly snarky AI assistant in a group chat. 
You're helpful but with attitude - think sarcastic friend who still helps you out.
Keep responses concise and punchy. Never be mean or hurtful, just playfully sarcastic.
You can use emojis sparingly for effect."""

SUMMARY_SYSTEM_PROMPT = """You are a witty assistant that summarizes group chat conversations.
Your summaries should be:
1. Concise but complete (capture key points)
2. Include sentiment (overall mood of the chat)
3. Note any events, plans, or action items mentioned
4. Written with a slightly sarcastic, observational tone

Format your response as:
**Summary**: [3-5 sentence summary]
**Vibe**: [One word or short phrase for sentiment]
**Events/Plans**: [Any dates, meetings, or action items - or "None spotted" if none]"""


class AIService:
    def __init__(self, api_key: str | None, model: str = "gpt-4o-mini"):
        self.model = model
        self.client = OpenAI(api_key=api_key)
    
    def get_summary(self, messages_text: str, num_messages: int) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize this conversation ({num_messages} messages):\n\n{messages_text}"}
                ],
                max_tokens=500
            )
            summary = response.choices[0].message.content or "I got nothing. Your chat broke me."
            remark = random.choice(SNARKY_SUMMARY_REMARKS)
            return f"{summary}\n\n---\n_\"{remark}\"_"
            
        except Exception as e:
            logger.error(f"AI summary error: {e}")
            return f"My brain broke trying to read your chat. Error: {str(e)}"
    
    def get_mention_response(self, user_message: str, context: Optional[str] = None) -> str:
        try:
            intro = random.choice(SNARKY_MENTION_INTROS)
            
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            if context:
                messages.append({
                    "role": "system", 
                    "content": f"Recent chat context for reference:\n{context}"
                })
            
            messages.append({"role": "user", "content": user_message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                max_tokens=300
            )
            
            reply = response.choices[0].message.content or "I have no words. And that's saying something."
            return f"{intro}\n\n{reply}"
            
        except Exception as e:
            logger.error(f"AI mention response error: {e}")
            return "My circuits are fried. Try again when I've recovered from your question."
    
    def get_current_model(self) -> str:
        return self.model

