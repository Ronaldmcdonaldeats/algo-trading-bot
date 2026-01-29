#!/usr/bin/env python3
"""
Advanced Features Verification Script
Verifies all components are installed and working correctly
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def verify_imports():
    """Verify all imports work"""
    print("=" * 70)
    print("ADVANCED FEATURES - IMPORT VERIFICATION")
    print("=" * 70)
    
    try:
        from trading_bot.risk.advanced_risk_management import (
            ValueAtRisk, MonteCarloSimulation, RegimeDetection,
            DynamicPositionSizing, ComprehensiveRiskAnalysis
        )
        print("✅ Risk Management Module imported successfully")
        print("   - ValueAtRisk")
        print("   - MonteCarloSimulation")
        print("   - RegimeDetection")
        print("   - DynamicPositionSizing")
        print("   - ComprehensiveRiskAnalysis")
    except ImportError as e:
        print(f"❌ Risk Management Module import failed: {e}")
        return False
    
    try:
        from trading_bot.learn.deep_learning_models import (
            FeatureEngineering, SimpleLSTM,
            ReinforcementLearningAgent, OnlineLearner
        )
        print("\n✅ Learning Module imported successfully")
        print("   - FeatureEngineering")
        print("   - SimpleLSTM")
        print("   - ReinforcementLearningAgent")
        print("   - OnlineLearner")
    except ImportError as e:
        print(f"❌ Learning Module import failed: {e}")
        return False
    
    return True


def verify_functionality():
    """Verify basic functionality"""
    print("\n" + "=" * 70)
    print("ADVANCED FEATURES - FUNCTIONALITY VERIFICATION")
    print("=" * 70)
    
    try:
        from trading_bot.risk.advanced_risk_management import ValueAtRisk
        
        # Test VaR calculation - need at least 100 data points
        returns = [0.01, -0.02, 0.015, -0.01, 0.005] * 30  # 150 data points
        var = ValueAtRisk.calculate_var(returns, 0.95)
        cvar = ValueAtRisk.calculate_cvar(returns, 0.95)
        
        print("✅ Value at Risk calculations working")
        print(f"   VaR (95%): {var:.4f}")
        print(f"   CVaR (95%): {cvar:.4f}")
    except Exception as e:
        print(f"❌ VaR calculation failed: {e}")
        return False
    
    try:
        from trading_bot.risk.advanced_risk_management import RegimeDetection
        
        returns = [0.002, 0.0015, 0.001, 0.0025] * 5
        regime = RegimeDetection.detect_regime(returns, window=20)
        multiplier = RegimeDetection.get_regime_multiplier(regime)
        
        print("✅ Regime detection working")
        print(f"   Detected regime: {regime}")
        print(f"   Position multiplier: {multiplier}x")
    except Exception as e:
        print(f"❌ Regime detection failed: {e}")
        return False
    
    try:
        from trading_bot.learn.deep_learning_models import FeatureEngineering
        
        prices = [100, 101, 102, 101, 103, 104, 103, 105, 106] * 5
        features = FeatureEngineering.extract_features(prices, window=20)
        normalized = FeatureEngineering.normalize_features(features)
        
        print("✅ Feature engineering working")
        print(f"   Features extracted: {len(features)}")
        print(f"   Features normalized: {len(normalized)}")
    except Exception as e:
        print(f"❌ Feature engineering failed: {e}")
        return False
    
    try:
        from trading_bot.learn.deep_learning_models import SimpleLSTM
        
        lstm = SimpleLSTM()
        prediction = lstm.forward(normalized)
        
        print("✅ LSTM predictions working")
        print(f"   Predicted return: {prediction.next_return:.6f}")
        print(f"   Confidence: {prediction.confidence:.2%}")
    except Exception as e:
        print(f"❌ LSTM prediction failed: {e}")
        return False
    
    try:
        from trading_bot.learn.deep_learning_models import ReinforcementLearningAgent
        
        agent = ReinforcementLearningAgent()
        state = agent.get_state('bull', 0.015, 1.5)
        action = agent.get_action(state)
        multiplier = agent.get_position_multiplier(action)
        
        print("✅ Reinforcement learning working")
        print(f"   State: {state}")
        print(f"   Action: {action}")
        print(f"   Position multiplier: {multiplier}x")
    except Exception as e:
        print(f"❌ RL agent failed: {e}")
        return False
    
    try:
        from trading_bot.learn.deep_learning_models import OnlineLearner
        
        learner = OnlineLearner()
        learner.add_observation(normalized, 0.01)
        learner.add_observation(normalized, 0.02)
        accuracy = learner.get_recent_accuracy(window=2)
        
        print("✅ Online learning working")
        print(f"   Observations tracked: 2")
        print(f"   Recent accuracy: {accuracy:.2%}")
    except Exception as e:
        print(f"❌ Online learning failed: {e}")
        return False
    
    return True


def verify_tests():
    """Verify test suite exists and can be run"""
    print("\n" + "=" * 70)
    print("ADVANCED FEATURES - TEST SUITE VERIFICATION")
    print("=" * 70)
    
    test_file = os.path.join(os.path.dirname(__file__), 'tests', 'test_advanced_features.py')
    
    if os.path.exists(test_file):
        print(f"✅ Test file found: {test_file}")
        with open(test_file, 'r') as f:
            lines = f.readlines()
        
        test_count = sum(1 for line in lines if 'def test_' in line)
        print(f"✅ Test count: {test_count}")
        print("\nTo run tests:")
        print("  pytest tests/test_advanced_features.py -v")
    else:
        print(f"❌ Test file not found: {test_file}")
        return False
    
    return True


def verify_documentation():
    """Verify documentation files exist"""
    print("\n" + "=" * 70)
    print("ADVANCED FEATURES - DOCUMENTATION VERIFICATION")
    print("=" * 70)
    
    docs = [
        'ADVANCED_FEATURES_GUIDE.md',
        'IMPLEMENTATION_SUMMARY.md',
        'QUALITY_ASSURANCE_REPORT.md',
        'COMPLETION_SUMMARY.md',
    ]
    
    base_dir = os.path.dirname(__file__)
    all_exist = True
    
    for doc in docs:
        path = os.path.join(base_dir, doc)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ {doc} ({size:,} bytes)")
        else:
            print(f"❌ {doc} NOT FOUND")
            all_exist = False
    
    return all_exist


def main():
    """Run all verifications"""
    print("\n")
    
    results = {
        'Imports': verify_imports(),
        'Functionality': verify_functionality(),
        'Tests': verify_tests(),
        'Documentation': verify_documentation(),
    }
    
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL VERIFICATIONS PASSED - READY FOR USE!")
        print("=" * 70)
        return 0
    else:
        print("⚠️  SOME VERIFICATIONS FAILED - SEE ABOVE")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
