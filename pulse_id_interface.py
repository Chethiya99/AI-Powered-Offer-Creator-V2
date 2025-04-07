import streamlit as st
import openai
import json
import re
from datetime import datetime, timedelta
import speech_recognition as sr
from audio_recorder_streamlit import audio_recorder

# Initialize session state
if 'offer_params' not in st.session_state:
    st.session_state.offer_params = None
if 'offer_created' not in st.session_state:
    st.session_state.offer_created = False
if 'adjusted_params' not in st.session_state:
    st.session_state.adjusted_params = None
if 'audio_bytes' not in st.session_state:
    st.session_state.audio_bytes = None

# Helper function for consistent dollar formatting
def format_currency(amount):
    return f"\\${amount}"  # Escaped for Markdown

# Function to transcribe audio
def transcribe_audio(audio_bytes):
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_bytes) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
    except Exception as e:
        st.error(f"Error transcribing audio: {str(e)}")
        return None

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")
st.markdown("Describe your offer in plain English (speak or type), and let AI extract the details for you!")

# Securely input OpenAI API key
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")

if not openai_api_key:
    st.warning("Please enter your OpenAI API key to proceed.")
    st.stop()

# Voice input section
st.subheader("🎤 Voice Input")
audio_bytes = audio_recorder("Click to speak your offer:", pause_threshold=2.0)

if audio_bytes:
    st.session_state.audio_bytes = audio_bytes
    st.audio(audio_bytes, format="audio/wav")
    
    if st.button("Transcribe Audio"):
        with st.spinner("Transcribing your voice..."):
            transcription = transcribe_audio(audio_bytes)
            if transcription:
                st.session_state.transcribed_text = transcription
                st.success("Transcription successful!")
                st.text_area("Transcribed Text:", value=transcription, height=100, key="transcription_display")

# Text input section with better examples
st.subheader("✏️ Text Input")
user_prompt = st.text_area(
    "Or type your offer description here (e.g., 'Give \\$20 cashback for first 10 customers spending \\$500+ in 7 days'):",
    height=100,
    help="Use dollar signs normally - we'll handle the formatting automatically",
    key="text_input",
    value=st.session_state.get("transcribed_text", "")
)

# Use whichever input is available (voice transcription takes precedence)
final_prompt = st.session_state.get("transcribed_text", user_prompt)

# Enhanced extraction function
def extract_offer_parameters(prompt, api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer details. Return JSON with:
                    {
                        "offer_type": "cashback/discount/free_shipping",
                        "value_type": "percentage/fixed",
                        "value": 20,
                        "min_spend": 500,
                        "duration_days": 7,
                        "audience": "all/premium/etc",
                        "offer_name": "creative name",
                        "max_redemptions": null,
                        "conditions": [],
                        "description": "marketing text"
                    }"""
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        if response and response.choices:
            content = response.choices[0].message.content.strip()
            content = re.sub(r'```json\n?(.*?)\n?```', r'\1', content, flags=re.DOTALL)
            return json.loads(content)
        return None
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        return None

# Dynamic offer editor - NOW UPDATES SESSION STATE DIRECTLY
def offer_editor():
    cols = st.columns(2)
    with cols[0]:
        st.session_state.adjusted_params["offer_name"] = st.text_input(
            "Offer Name", 
            value=st.session_state.adjusted_params.get("offer_name", "")
        )
        st.session_state.adjusted_params["offer_type"] = st.selectbox(
            "Type",
            ["cashback", "discount", "free_shipping"],
            index=["cashback", "discount", "free_shipping"].index(
                st.session_state.adjusted_params.get("offer_type", "cashback")
            )
        )
        st.session_state.adjusted_params["value"] = st.number_input(
            "Percentage (%)" if st.session_state.adjusted_params.get("value_type") == "percentage" else "Amount ($)",
            value=st.session_state.adjusted_params.get("value", 0),
            key="value_input"
        )
    
    with cols[1]:
        st.session_state.adjusted_params["min_spend"] = st.number_input(
            "Minimum Spend ($)",
            value=st.session_state.adjusted_params.get("min_spend", 0),
            key="min_spend_input"
        )
        st.session_state.adjusted_params["duration_days"] = st.number_input(
            "Duration (Days)",
            value=st.session_state.adjusted_params.get("duration_days", 7),
            key="duration_input"
        )
        if st.session_state.adjusted_params.get("max_redemptions"):
            st.session_state.adjusted_params["max_redemptions"] = st.number_input(
                "Max Redemptions",
                value=st.session_state.adjusted_params.get("max_redemptions"),
                key="max_redemptions_input"
            )

# Offer display component
def display_offer(params):
    end_date = datetime.now() + timedelta(days=params.get("duration_days", 7))
    value_display = f"{params['value']}%" if params.get("value_type") == "percentage" else format_currency(params['value'])
    
    with st.container():
        st.markdown("---")
        st.subheader("🎉 Your Created Offer")
        cols = st.columns([1, 3])
        
        with cols[0]:
            icon = "💰" if params.get("offer_type") == "cashback" else "🏷️"
            st.markdown(f"<h1 style='text-align: center;'>{icon}</h1>", unsafe_allow_html=True)
        
        with cols[1]:
            st.markdown(f"""
            **✨ {params.get('offer_name', 'Special Offer')}**  
            💵 **{value_display}** {params.get('offer_type')}  
            🛒 Min. spend: **{format_currency(params.get('min_spend', 0))}**  
            ⏳ Valid until: **{end_date.strftime('%b %d, %Y')}**  
            👥 For: **{params.get('audience', 'all customers').title()}**
            """, unsafe_allow_html=True)
            
            if params.get("conditions"):
                st.markdown("**Conditions:**")
                for condition in params["conditions"]:
                    st.markdown(f"- {condition}")
    
    st.markdown("---")
    st.success("Offer updated successfully!")

# Main workflow
if st.button("Generate Offer") and final_prompt:
    with st.spinner("Creating your offer..."):
        st.session_state.offer_params = extract_offer_parameters(final_prompt, openai_api_key)
        st.session_state.adjusted_params = st.session_state.offer_params.copy()
        st.session_state.offer_created = True
        st.rerun()

if st.session_state.offer_params:
    st.success("✅ Offer parameters extracted!")
    
    # Display raw parameters (with formatted currency)
    params_display = st.session_state.offer_params.copy()
    if 'min_spend' in params_display:
        params_display['min_spend'] = format_currency(params_display['min_spend'])
    st.json(params_display)

if st.session_state.offer_created and st.session_state.adjusted_params:
    st.success("✅ Adjust the offer below and see changes in real-time:")
    
    # Edit form - NOW DIRECTLY MODIFIES SESSION STATE
    offer_editor()
    
    # Display the CURRENTLY EDITED offer (not the original)
    display_offer(st.session_state.adjusted_params)
    
    if st.button("🔄 Refresh Preview"):
        st.rerun()
