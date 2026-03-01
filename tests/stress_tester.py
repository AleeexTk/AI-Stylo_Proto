import random
import time
import json
from pathlib import Path

# Список можливих дій користувача
USER_ACTIONS = [
    "change_gender",
    "upload_photo",
    "select_item",
    "generate_viz",
    "change_budget",
    "change_style",
    "reset_profile",
    "ai_query",
    "save_lookbook",
    "check_skills"
]

class StyloPressureTester:
    """Симулятор випадкової поведінки користувача для стрес-тестування AI-Stylo"""
    
    def __init__(self, base_url="http://localhost:8501"):
        self.base_url = base_url
        self.results = []

    def generate_scenario(self, steps=5):
        """Створює ланцюжок випадкових дій"""
        scenario = random.choices(USER_ACTIONS, k=steps)
        return scenario

    def run_suite(self, num_scenarios=10):
        print(f"🚀 Запуск {num_scenarios} випадкових сценаріїв тестування...")
        for i in range(num_scenarios):
            scenario = self.generate_scenario(random.randint(3, 7))
            print(f"📋 Сценарій #{i+1}: {' -> '.join(scenario)}")
            # У реальному середовищі тут був би виклик Playwright/Selenium
            # Для прототипу ми логуємо очікувану поведінку
            self.results.append({
                "scenario_id": i + 1,
                "steps": scenario,
                "status": "planned"
            })
        
        # Збереження плану тестування
        output_path = Path("tests/stress_test_plan.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=4, ensure_ascii=False)
        print(f"✅ План тестування збережено у {output_path}")

if __name__ == "__main__":
    tester = StyloPressureTester()
    tester.run_suite(10)
