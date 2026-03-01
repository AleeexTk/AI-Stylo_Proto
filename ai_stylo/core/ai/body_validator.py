"""
Body Validator — анализирует результаты GridMapper для оценки
качества кадра, полноты позы и выдает рекомендации.
"""

from typing import Dict, List, Any
from apps.core.ai.grid_mapper import GridResult

class BodyValidator:
    """Анализирует GridResult на предмет корректности и пригодности для TryOn."""
    
    @staticmethod
    def validate(grid_result: GridResult) -> Dict[str, Any]:
        """Возвращает детальный отчет о теле в кадре."""
        
        issues = []
        is_ready = True
        
        # 1. Проверка полноты
        if grid_result.completeness < 0.5:
            is_ready = False
            issues.append("Low completeness score. Expected at least 50% of the body visible.")
            
        # 2. Проверка базовых частей тела
        detected = grid_result.detected_zones
        if "head" not in detected:
            issues.append("Head not detected. Avatar alignment might be incorrect.")
        if "torso" not in detected:
            is_ready = False
            issues.append("Torso not detected. Cannot proceed with Torso-based clothing.")
            
        # 3. Проверка позы
        if grid_result.pose_type == "unknown":
            is_ready = False
            issues.append("Pose is unrecognizable.")
        elif grid_result.pose_type == "selfie":
            issues.append("Selfie pose detected. Arms might overlap with the torso.")
            
        # 4. Проверка полноразмерности
        if grid_result.partial:
            issues.append("Legs not detected in the frame. Only upper-body items will render correctly.")
            
        return {
            "is_ready_for_tryon": is_ready,
            "completeness": grid_result.completeness,
            "pose_type": grid_result.pose_type,
            "is_full_body": not grid_result.partial,
            "issues": issues,
            "detected_zones": detected
        }
