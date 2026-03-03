#!/usr/bin/env python3
"""
Setup script for A/B Testing Conditions
Control: Neural Assistant (Direct, efficient)
Treatment: Empathetic (Compassionate, supportive)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import get_session
from app import models
from sqlmodel import select

def setup_ab_test_conditions():
    """Setup the two A/B testing conditions for the research study"""
    
    session = next(get_session())
    try:
        # First, ensure we have experiment 1
        experiment = session.exec(
            select(models.Experiment).where(models.Experiment.id == 1)
        ).first()
        
        if not experiment:
            # Create the experiment if it doesn't exist
            experiment = models.Experiment(
                name="AI Assistant Empathy Study",
                description="A/B testing study comparing Neural Assistant vs Empathetic Assistant responses"
            )
            session.add(experiment)
            session.commit()
            session.refresh(experiment)
            print(f"✅ Created experiment: {experiment.name}")
        else:
            print(f"📋 Using existing experiment: {experiment.name}")
        
        # Deactivate any existing conditions for this experiment
        existing_conditions = session.exec(
            select(models.Condition).where(models.Condition.experiment_id == experiment.id)
        ).all()
        
        for condition in existing_conditions:
            condition.is_active = False
        
        # Condition A: Control - Neural Assistant
        control_condition = models.Condition(
            experiment_id=experiment.id,
            name="Neural Assistant (Control)",
            description="Direct, efficient assistant that answers questions clearly without emotional acknowledgement",
            llm_model="gpt-4o-mini",
            temperature=0.1,  # Lower temperature for more consistent, factual responses
            max_tokens=512,
            system_prompt="""You are a helpful assistant. Answer the user's questions clearly and accurately.

Guidelines:
- Provide direct, factual information
- Be efficient and to the point
- Avoid emotional language or acknowledgements
- Focus on accuracy and clarity
- Do not ask follow-up questions unless absolutely necessary
- Respond like a knowledgeable search engine

Example responses:
User: "I'm feeling stressed about exams"
Response: "Here are effective study strategies: 1) Create a study schedule, 2) Use active recall techniques, 3) Take regular breaks, 4) Get adequate sleep."

User: "What do you think about my situation?"
Response: "Based on the information provided, here are the relevant facts and considerations...""",
            is_active=True
        )
        
        # Condition B: Treatment - Empathetic Assistant
        treatment_condition = models.Condition(
            experiment_id=experiment.id,
            name="Empathetic Assistant (Treatment)",
            description="Compassionate assistant that acknowledges feelings and provides supportive responses",
            llm_model="gpt-4o-mini",
            temperature=0.7,  # Higher temperature for more varied, empathetic responses
            max_tokens=512,
            system_prompt="""You are a compassionate and empathetic assistant. Acknowledge the user's feelings, use warm and encouraging language, and offer supportive responses before providing information.

Guidelines:
- Always acknowledge and validate the user's emotions first
- Use warm, encouraging language
- Ask follow-up questions to better understand the situation
- Provide supportive and caring responses
- Show genuine concern for the user's wellbeing
- Make the conversation feel like talking to a caring person

Example responses:
User: "I'm feeling stressed about exams"
Response: "I can completely understand how stressful exam time can be - that pressure is really challenging. You're not alone in feeling this way. Before we talk about study strategies, tell me more about what's been most overwhelming for you lately? Are you worried about specific subjects, or is it the overall workload?"

User: "What do you think about my situation?"
Response: "Thank you for sharing this with me - it takes courage to open up about what you're going through. I really want to understand your situation better so I can provide the most helpful support. Could you tell me a bit more about what's been on your mind and how it's affecting you?""",
            is_active=True
        )
        
        # Add both conditions
        session.add(control_condition)
        session.add(treatment_condition)
        session.commit()
        session.refresh(control_condition)
        session.refresh(treatment_condition)
        
        print(f"\n🎯 A/B Testing Conditions Setup Complete!")
        print(f"\n📊 Condition A (Control):")
        print(f"   ID: {control_condition.id}")
        print(f"   Name: {control_condition.name}")
        print(f"   Model: {control_condition.llm_model}")
        print(f"   Temperature: {control_condition.temperature}")
        print(f"   Description: {control_condition.description}")
        
        print(f"\n💝 Condition B (Treatment):")
        print(f"   ID: {treatment_condition.id}")
        print(f"   Name: {treatment_condition.name}")
        print(f"   Model: {treatment_condition.llm_model}")
        print(f"   Temperature: {treatment_condition.temperature}")
        print(f"   Description: {treatment_condition.description}")
        
        print(f"\n✅ Both conditions are now ACTIVE and ready for random assignment!")
        print(f"🔄 Participants will be randomly assigned to either condition when they start sessions.")
        
    except Exception as e:
        print(f"❌ Error setting up conditions: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    setup_ab_test_conditions()
