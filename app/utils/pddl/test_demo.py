# app/utils/pddl/test_demo.py
import sys
import os
from typing import Dict, List, Optional, Any

# Fix the import - use the full module path
from app.utils.pddl.pddl_classes import *
from app.utils.pddl.pddl_client import ModelClient
from app.utils.pddl.main import *  # Import everything from main module

def simple_test():
    """Test just the core functionality without LLM calls"""
    print("Testing PDDL System...")
    
    try:
        # Test 1: Create sample data
        print("1. Creating sample tasks...")
        state = create_sample_contracted_tasks()  # Direct function call
        print(f"   Created {len(state.tasks)} tasks")
        
        # Test 2: Contract validation only
        print("2. Testing contract validation...")
        validator = ContractValidator()  # Direct class instantiation
        
        auth_task = state.tasks["auth_system"]
        valid_inputs = {
            "user_data": {"username": "test", "password": "12345678"},
            "auth_config": {"jwt_secret": "secret", "expiry_time": 3600}
        }
        
        errors = validator.validate_task_inputs(auth_task, valid_inputs)
        print(f"   Validation result: {len(errors)} errors")
        
        # Test 3: PDDL generation
        print("3. Testing PDDL generation...")
        generator = PDDLGenerator()  # Direct class instantiation
        domain = generator.generate_domain(state)
        print(f"   Generated PDDL domain: {len(domain)} characters")
        
        print("Core tests passed!")
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    simple_test()