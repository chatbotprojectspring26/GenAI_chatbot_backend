#!/usr/bin/env python3

import sqlite3
import json

def check_database():
    conn = sqlite3.connect('dev.db')
    cursor = conn.cursor()
    
    print("=== EXPERIMENTS ===")
    cursor.execute("SELECT id, name FROM experiment")
    experiments = cursor.fetchall()
    for exp in experiments:
        print(f"ID: {exp[0]}, Name: {exp[1]}")
    
    print("\n=== CONDITIONS ===")
    cursor.execute("SELECT id, name, experiment_id FROM condition")
    conditions = cursor.fetchall()
    for cond in conditions:
        print(f"ID: {cond[0]}, Name: {cond[1]}, Experiment ID: {cond[2]}")
    
    print("\n=== ACTIVE CONDITIONS ===")
    for exp_id, exp_name in experiments:
        cursor.execute("SELECT id, name FROM condition WHERE experiment_id = ?", (exp_id,))
        active_conds = cursor.fetchall()
        if active_conds:
            print(f"Experiment {exp_id} ({exp_name}):")
            for cond in active_conds:
                print(f"  - Condition {cond[0]}: {cond[1]}")
    
    conn.close()

if __name__ == "__main__":
    check_database()
