#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import init_db, get_session
from app import models, services
from sqlmodel import Session, select

def create_test_data():
    # Initialize database
    init_db()
    
    with next(get_session()) as db:
        # Check if experiment already exists
        existing_exp = db.exec(select(models.Experiment).where(models.Experiment.name == "Test Experiment")).first()
        if existing_exp:
            print("Test experiment already exists")
            return existing_exp.id
        
        # Create experiment
        experiment = models.Experiment(
            name="Test Experiment",
            description="A test experiment for development",
            status="active"
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        
        # Create condition
        condition = models.Condition(
            experiment_id=experiment.id,
            name="Test Condition",
            description="A test condition for development",
            llm_model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=512,
            system_prompt="You are a helpful AI assistant. Please respond in a friendly and helpful manner.",
            is_active=True
        )
        db.add(condition)
        db.commit()
        db.refresh(condition)
        
        print(f"Created experiment with ID: {experiment.id}")
        print(f"Created condition with ID: {condition.id}")
        
        return experiment.id

if __name__ == "__main__":
    create_test_data()
