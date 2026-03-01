"""
Grid Mapper — проецирует pose keypoints (MediaPipe/простые) на сетку 10×30.

Сетка 10 колонок × 30 строк = 300 секторов.
Каждый сектор получает метку зоны тела:
  BACKGROUND, HEAD, TORSO, L_ARM, R_ARM, L_LEG, R_LEG, UNKNOWN

Использование:
    from ai_stylo.core.ai.grid_mapper import GridMapper

    gm = GridMapper()
    result = gm.map(keypoints, image_w=480, image_h=640)
    # result.grid_labels  — 30×10 list[list[str]]
    # result.occupied     — list[tuple[row, col]]
    # result.zones        — dict zone → list[sectors]
    # result.grid_points  — 30×10 normalized [x,y] (для тепловой карты)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

COLS = 10
ROWS = 30

# Зоны тела
BACKGROUND = "background"
HEAD       = "head"
TORSO      = "torso"
L_ARM      = "l_arm"
R_ARM      = "r_arm"
L_LEG      = "l_leg"
R_LEG      = "r_leg"
UNKNOWN    = "unknown"

# Индексы MediaPipe Pose (17 keypoints, 0-indexed)
KP = {
    "nose":           0,
    "left_eye":       1,
    "right_eye":      2,
    "left_ear":       3,
    "right_ear":      4,
    "left_shoulder":  5,
    "right_shoulder": 6,
    "left_elbow":     7,
    "right_elbow":    8,
    "left_wrist":     9,
    "right_wrist":    10,
    "left_hip":       11,
    "right_hip":      12,
    "left_knee":      13,
    "right_knee":     14,
    "left_ankle":     15,
    "right_ankle":    16,
}


@dataclass
class GridResult:
    grid_labels: List[List[str]]            # [row][col] → zone label
    grid_points: List[List[List[float]]]    # [row][col] → [x_norm, y_norm]
    occupied: List[Tuple[int, int]]         # сектора с телом (не background)
    zones: Dict[str, List[Tuple[int, int]]] # zone → список (row, col)
    completeness: float                     # 0.0–1.0
    detected_zones: List[str]               # список обнаруженных зон
    partial: bool                           # True если ног нет в кадре
    pose_type: str                          # straight / tilted / arms_up / selfie


class GridMapper:
    """Маппер keypoints → grid 10×30."""

    def __init__(self, cols: int = COLS, rows: int = ROWS):
        self.cols = cols
        self.rows = rows

    # ------------------------------------------------------------------
    # Основной метод
    # ------------------------------------------------------------------
    def map(
        self,
        keypoints: List[Optional[Tuple[float, float]]],  # list[17] (x_px, y_px) или None
        image_w: int,
        image_h: int,
    ) -> GridResult:
        """
        keypoints: список из 17 элементов [(x_px, y_px) | None].
        Возвращает GridResult.
        """
        # 1. Инициализируем сетку
        grid = [[BACKGROUND] * self.cols for _ in range(self.rows)]
        grid_pts = [
            [
                [c / self.cols + 1 / (2 * self.cols), r / self.rows + 1 / (2 * self.rows)]
                for c in range(self.cols)
            ]
            for r in range(self.rows)
        ]

        # 2. Нормализуем keypoints
        kp_norm = self._normalize(keypoints, image_w, image_h)

        # 3. Анализируем bbox тела
        present = {name: kp_norm[idx] for name, idx in KP.items() if kp_norm[idx] is not None}
        if not present:
            return self._empty_result(grid_pts)

        # 4. Строим body bbox и окрашиваем сектора
        self._paint_head(grid, kp_norm)
        self._paint_torso(grid, kp_norm)
        self._paint_arm(grid, kp_norm, side="left")
        self._paint_arm(grid, kp_norm, side="right")
        self._paint_leg(grid, kp_norm, side="left")
        self._paint_leg(grid, kp_norm, side="right")

        # 5. Собираем zones / occupied
        zones: Dict[str, List[Tuple[int, int]]] = {}
        occupied = []
        for r in range(self.rows):
            for c in range(self.cols):
                label = grid[r][c]
                if label != BACKGROUND:
                    occupied.append((r, c))
                    zones.setdefault(label, []).append((r, c))

        detected = list(zones.keys())
        partial = (L_LEG not in detected and R_LEG not in detected)
        completeness = self._calc_completeness(detected, partial)
        pose_type = self._classify_pose(kp_norm)

        return GridResult(
            grid_labels=grid,
            grid_points=grid_pts,
            occupied=occupied,
            zones=zones,
            completeness=completeness,
            detected_zones=detected,
            partial=partial,
            pose_type=pose_type,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize(
        self,
        keypoints: List[Optional[Tuple[float, float]]],
        w: int,
        h: int,
    ) -> List[Optional[Tuple[float, float]]]:
        """Нормализует пиксельные координаты в [0,1]."""
        result = []
        for kp in keypoints:
            if kp is None:
                result.append(None)
            else:
                result.append((kp[0] / w, kp[1] / h))
        return result

    def _px_to_sector(self, x_norm: float, y_norm: float) -> Tuple[int, int]:
        col = min(int(x_norm * self.cols), self.cols - 1)
        row = min(int(y_norm * self.rows), self.rows - 1)
        return row, col

    def _fill_rect(self, grid: List[List[str]], y0: float, y1: float, x0: float, x1: float, label: str):
        """Заполняет прямоугольный диапазон нормализованных координат."""
        r0 = max(0, int(y0 * self.rows))
        r1 = min(self.rows, int(y1 * self.rows) + 1)
        c0 = max(0, int(x0 * self.cols))
        c1 = min(self.cols, int(x1 * self.cols) + 1)
        for r in range(r0, r1):
            for c in range(c0, c1):
                if grid[r][c] == BACKGROUND:
                    grid[r][c] = label

    def _paint_head(self, grid, kp):
        nose = kp[KP["nose"]]
        l_ear = kp[KP["left_ear"]]
        r_ear = kp[KP["right_ear"]]
        pts = [p for p in [nose, l_ear, r_ear] if p]
        if not pts:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        r = 0.08  # ~радиус головы в нормализованных единицах
        self._fill_rect(grid, cy - r, cy + r, cx - r, cx + r, HEAD)

    def _paint_torso(self, grid, kp):
        ls = kp[KP["left_shoulder"]]
        rs = kp[KP["right_shoulder"]]
        lh = kp[KP["left_hip"]]
        rh = kp[KP["right_hip"]]
        pts = [p for p in [ls, rs, lh, rh] if p]
        if len(pts) < 2:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self._fill_rect(grid, min(ys), max(ys), min(xs) - 0.02, max(xs) + 0.02, TORSO)

    def _paint_arm(self, grid, kp, side: str):
        if side == "left":
            shoulder = kp[KP["left_shoulder"]]
            elbow    = kp[KP["left_elbow"]]
            wrist    = kp[KP["left_wrist"]]
            label    = L_ARM
        else:
            shoulder = kp[KP["right_shoulder"]]
            elbow    = kp[KP["right_elbow"]]
            wrist    = kp[KP["right_wrist"]]
            label    = R_ARM

        chain = [p for p in [shoulder, elbow, wrist] if p]
        for i in range(len(chain) - 1):
            p0, p1 = chain[i], chain[i + 1]
            x0, x1 = sorted([p0[0], p1[0]])
            y0, y1 = sorted([p0[1], p1[1]])
            self._fill_rect(grid, y0 - 0.02, y1 + 0.02, x0 - 0.02, x1 + 0.02, label)

    def _paint_leg(self, grid, kp, side: str):
        if side == "left":
            hip   = kp[KP["left_hip"]]
            knee  = kp[KP["left_knee"]]
            ankle = kp[KP["left_ankle"]]
            label = L_LEG
        else:
            hip   = kp[KP["right_hip"]]
            knee  = kp[KP["right_knee"]]
            ankle = kp[KP["right_ankle"]]
            label = R_LEG

        chain = [p for p in [hip, knee, ankle] if p]
        for i in range(len(chain) - 1):
            p0, p1 = chain[i], chain[i + 1]
            x0, x1 = sorted([p0[0], p1[0]])
            y0, y1 = sorted([p0[1], p1[1]])
            self._fill_rect(grid, y0, y1, x0 - 0.03, x1 + 0.03, label)

    def _calc_completeness(self, detected: List[str], partial: bool) -> float:
        """
        Оценка полноты кадра:
          head=0.15, torso=0.35, arms=0.25 (каждая 0.125), legs=0.25 (каждая 0.125)
        """
        score = 0.0
        weights = {
            HEAD:  0.15,
            TORSO: 0.35,
            L_ARM: 0.125,
            R_ARM: 0.125,
            L_LEG: 0.125,
            R_LEG: 0.125,
        }
        for zone, w in weights.items():
            if zone in detected:
                score += w
        return round(min(1.0, score), 3)

    def _classify_pose(self, kp) -> str:
        """Определяет тип позы по положению запястий относительно плеч."""
        l_wrist = kp[KP["left_wrist"]]
        r_wrist = kp[KP["right_wrist"]]
        l_shoulder = kp[KP["left_shoulder"]]
        r_shoulder = kp[KP["right_shoulder"]]

        if not l_shoulder or not r_shoulder:
            return "unknown"

        shoulder_y = (l_shoulder[1] + r_shoulder[1]) / 2

        # Руки подняты выше плеч?
        wrists_up = sum(
            1 for w in [l_wrist, r_wrist] if w and w[1] < shoulder_y - 0.05
        )
        if wrists_up >= 1:
            return "selfie"  # часто при селфи рука поднята

        # Наклон плеч
        tilt = abs(l_shoulder[1] - r_shoulder[1])
        if tilt > 0.05:
            return "tilted"

        return "straight"

    def _empty_result(self, grid_pts) -> GridResult:
        grid = [[BACKGROUND] * self.cols for _ in range(self.rows)]
        return GridResult(
            grid_labels=grid,
            grid_points=grid_pts,
            occupied=[],
            zones={},
            completeness=0.0,
            detected_zones=[],
            partial=True,
            pose_type="unknown",
        )
