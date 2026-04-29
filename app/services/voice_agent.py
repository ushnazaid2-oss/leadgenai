"""
AI Voice Agent — Simplified Phase 1 using Twilio <Gather> + OpenAI GPT.
Architecture: Speech → Text → GPT → Response → Twilio <Say>
Designed to be upgradable to real-time streaming later.
"""

import logging
import json
from typing import Optional
from datetime import datetime

from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Gather
import openai
import httpx

from app.config import settings
from app.services.circuit_breaker import twilio_circuit, openai_circuit

logger = logging.getLogger(__name__)


class VoiceAgent:
    """
    AI-powered calling agent using Twilio Voice + OpenAI GPT.

    Phase 1 (current): Gather-based loop
      1. Twilio calls lead
      2. <Gather> captures speech → text
      3. GPT processes text with call script context
      4. <Say> speaks GPT response back
      5. Loop until conversation ends

    Phase 2 (future upgrade): Real-time Media Streams
    """

    DEFAULT_SYSTEM_PROMPT = """You are a professional AI sales agent making an outbound call.
Follow the provided call script as a guide, but adapt naturally to the conversation.
Be warm, professional, and human-like. Never say you are an AI.
If asked questions outside the script, answer helpfully and steer back to the pitch.
Keep responses concise (2-3 sentences max for natural phone conversation).
If the person is interested, suggest scheduling a meeting.
If they're not interested, thank them politely and end the call."""

    @staticmethod
    def get_twilio_client() -> TwilioClient:
        """Get authenticated Twilio client."""
        return TwilioClient(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )

    @classmethod
    async def initiate_call(
        cls,
        to_number: str,
        from_number: Optional[str] = None,
        call_script: Optional[str] = None,
        lead_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
    ) -> dict:
        """
        Initiate an outbound AI call to a lead.
        Returns Twilio call SID and status.
        """
        from_num = from_number or settings.TWILIO_DEFAULT_FROM_NUMBER
        if not from_num:
            raise ValueError("No outbound phone number configured")

        # Build the webhook URL that Twilio will call when connected
        webhook_url = (
            f"{settings.TRACKING_BASE_URL}/api/calls/twilio-voice-webhook"
            f"?lead_id={lead_id or 0}"
            f"&campaign_id={campaign_id or 0}"
        )
        if call_script:
            import urllib.parse
            webhook_url += f"&script={urllib.parse.quote(call_script[:500])}"

        async def _make_call():
            client = cls.get_twilio_client()
            call = client.calls.create(
                to=to_number,
                from_=from_num,
                url=webhook_url,
                status_callback=f"{settings.TRACKING_BASE_URL}/api/calls/twilio-status",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                timeout=30,
                machine_detection="Enable",
            )
            return {"call_sid": call.sid, "status": call.status}

        return await twilio_circuit.call(_make_call)

    @classmethod
    def build_initial_greeting(cls, call_script: Optional[str] = None) -> str:
        """Build TwiML for the initial greeting when the call connects."""
        vr = VoiceResponse()

        # Opening greeting from the script or default
        if call_script:
            lines = call_script.strip().split("\n")
            greeting = lines[0] if lines else "Hello! How are you doing today?"
        else:
            greeting = (
                "Hello! This is a quick call about how we can help your business "
                "grow with our AI-powered solutions. Do you have a moment?"
            )

        gather = Gather(
            input="speech",
            action="/api/calls/twilio-gather-response",
            method="POST",
            speech_timeout="auto",
            language="en-US",
            timeout=5,
        )
        gather.say(greeting, voice="Polly.Joanna", language="en-US")
        vr.append(gather)

        # If no input, try once more
        vr.say("I didn't catch that. Let me call back another time. Goodbye!",
               voice="Polly.Joanna")
        vr.hangup()

        return str(vr)

    @classmethod
    async def process_speech_input(
        cls,
        speech_text: str,
        conversation_history: list,
        call_script: Optional[str] = None,
    ) -> str:
        """
        Process user speech through GPT and return AI response text.
        """
        system_prompt = cls.DEFAULT_SYSTEM_PROMPT
        if call_script:
            system_prompt += f"\n\n--- CALL SCRIPT ---\n{call_script}\n--- END SCRIPT ---"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": speech_text})

        async def _get_gpt_response():
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()

        try:
            return await openai_circuit.call(_get_gpt_response)
        except Exception as e:
            logger.error(f"GPT processing failed: {e}")
            return "I apologize, could you repeat that? I want to make sure I understand correctly."

    @classmethod
    def build_response_twiml(cls, ai_response: str, should_continue: bool = True) -> str:
        """Build TwiML response with AI-generated speech."""
        vr = VoiceResponse()

        if should_continue:
            gather = Gather(
                input="speech",
                action="/api/calls/twilio-gather-response",
                method="POST",
                speech_timeout="auto",
                language="en-US",
                timeout=8,
            )
            gather.say(ai_response, voice="Polly.Joanna", language="en-US")
            vr.append(gather)

            vr.say("Thank you for your time. Have a great day!", voice="Polly.Joanna")
            vr.hangup()
        else:
            vr.say(ai_response, voice="Polly.Joanna", language="en-US")
            vr.hangup()

        return str(vr)

    @classmethod
    async def classify_call_outcome(cls, transcript: str) -> dict:
        """
        Use GPT to classify call outcome and generate summary.
        Returns: {outcome, summary, is_hot_lead, meeting_requested}
        """
        prompt = f"""Analyze this phone call transcript and provide:
1. outcome: one of [interested, not_interested, follow_up, no_answer, voicemail]
2. summary: brief 2-3 sentence summary of the call
3. is_hot_lead: true if the person showed strong interest
4. meeting_requested: true if they agreed to or requested a meeting

Respond ONLY with valid JSON, no other text.

TRANSCRIPT:
{transcript}"""

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
            result_text = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(result_text)
        except Exception as e:
            logger.error(f"Call classification failed: {e}")
            return {
                "outcome": "follow_up",
                "summary": "Call completed. Classification failed.",
                "is_hot_lead": False,
                "meeting_requested": False,
            }

    @classmethod
    async def list_available_numbers(cls) -> list:
        """List all phone numbers in the Twilio account."""
        try:
            client = cls.get_twilio_client()
            numbers = client.incoming_phone_numbers.list()
            return [
                {
                    "phone_number": n.phone_number,
                    "friendly_name": n.friendly_name,
                    "country": n.phone_number[:2],
                    "capabilities": {
                        "voice": n.capabilities.get("voice", False),
                        "sms": n.capabilities.get("sms", False),
                    },
                }
                for n in numbers
            ]
        except Exception as e:
            logger.error(f"Failed to list Twilio numbers: {e}")
            return []

    @classmethod
    async def purchase_number(cls, country_code: str = "US", area_code: Optional[str] = None) -> dict:
        """Search for and purchase a Twilio phone number."""
        try:
            client = cls.get_twilio_client()
            kwargs = {"voice_enabled": True}
            if area_code:
                kwargs["area_code"] = area_code

            available = client.available_phone_numbers(country_code).local.list(**kwargs, limit=1)
            if not available:
                raise ValueError(f"No numbers available for {country_code}")

            purchased = client.incoming_phone_numbers.create(
                phone_number=available[0].phone_number
            )
            return {
                "phone_number": purchased.phone_number,
                "friendly_name": purchased.friendly_name,
                "sid": purchased.sid,
            }
        except Exception as e:
            logger.error(f"Number purchase failed: {e}")
            raise
