"""Interactive elements for parameter and event control."""
# pylint: disable=invalid-name,no-member
from functools import cache

import pygame


pygame.font.init()
font = pygame.font.SysFont("arial", 20, False)
TEXT_COLOR = (255, 255, 255)


def clamp(value: int | float, minimum: int | float, maximum: int | float) -> int | float:
    """Restrict a numerical value to a specified range."""
    return max(minimum, min(maximum, value))


class Variable:
    """Object binding for variables and their values."""
    def __init__(self, name: str, value):
        self.name = name
        self._value = value

    @property
    def value(self):
        """Value associated with a variable."""
        return self._value


class BooleanVariable(Variable):
    """Object binding for boolean variable."""
    def __init__(self, name: str, value: bool):
        super().__init__(name, value)

    @property
    def value(self) -> bool:
        return self._value

    @value.setter
    def value(self, value: bool):
        self._value = value


class NumericVariable(Variable):
    """Object binding for a numeric variable. Proactively handles value changes."""
    def __init__(self, name: str, value: int | float, event: int | None = None):
        super().__init__(name, value)
        self.event = event
        self.old = value

    @property
    def value(self) -> int | float:
        return self._value

    @value.setter
    def value(self, value: int | float):
        if self._value != value:
            self.old = self._value
            self._value = value
            if self.event:
                pygame.event.post(pygame.event.Event(self.event))

    def resolve_diff(self):
        """Resolves discrepancy between old and current value for condition handling."""
        self.old = self._value


class Button(pygame.sprite.Sprite):
    """Button bound to a pygame event."""
    border_color = (255, 255, 255)
    active_color = (128, 128, 128)
    inactive_color = (0, 0, 0, 0)
    border_thickness = 2
    padding = 5
    def __init__(self, label: str, center: tuple[int, int], event: int):
        super().__init__()
        self.label = font.render(label, True, TEXT_COLOR)
        self.size = (self.label.get_width() + 2*self.padding,
                     font.get_height() + 2*self.padding)
        self.center = center
        self.surf = pygame.Surface(self.size, pygame.SRCALPHA)
        adjusted_center = (center[0] + int(self.size[0]/2), center[1])
        self.rect = self.surf.get_rect(center=adjusted_center, size=self.size)
        self.event = event

    def update(self, mouse_buttons: tuple[bool, bool, bool],
               mouse_position: tuple[int, int]):
        """Draw the button and handle interactions."""
        self.surf.fill((0, 0, 0, 0))
        if self.rect.collidepoint(mouse_position) and mouse_buttons[0]:
            self.surf.fill(self.active_color)
        pygame.draw.rect(self.surf, self.border_color,
                         pygame.Rect((0, 0), self.size), self.border_thickness)
        self.surf.blit(self.label, (self.padding, self.padding))


class Checkbox(pygame.sprite.Sprite):
    """Checkbox bound to a boolean variable."""
    width = font.get_height()
    border_color = (255, 255, 255)
    active_color = (128, 128, 128, 255)
    inactive_color = (0, 0, 0, 0)
    border_thickness = 2
    def __init__(self, label: str, center: tuple[int, int],
                 variable: Variable, active: bool = False):
        super().__init__()
        self.label = font.render(label, True, TEXT_COLOR)
        self.size = (self.width + self.label.get_width() + 30, self.width)
        self.center = center
        self.surf = pygame.Surface(self.size, pygame.SRCALPHA)
        adjusted_center = (center[0] + int(self.size[0]/2), center[1])
        self.rect = self.surf.get_rect(center=adjusted_center, size=self.size)
        self.box_surf = pygame.Surface((self.width-2*self.border_thickness,
                                        self.width-2*self.border_thickness), pygame.SRCALPHA)
        self.variable = variable
        self.active = active
        self.box_surf.fill(self.active_color if self.active else self.inactive_color)

    def update(self):
        """Draw the checkbox and handle interactions."""
        self.surf.fill(self.inactive_color)
        pygame.draw.rect(self.surf, self.border_color,
                         pygame.Rect((0, 0), (self.width, self.width)), self.border_thickness)
        self.surf.blit(self.label, (self.width + 15, 0))
        self.surf.blit(self.box_surf, (self.border_thickness, self.border_thickness))

    def toggle(self):
        """Toggle the checkbox state between active and inactive."""
        self.active = not self.active
        self.box_surf.fill(self.active_color if self.active else self.inactive_color)
        self.variable.value = self.active  # type: ignore


class Slider(pygame.sprite.Sprite):
    """Slider bound to a numerical variable."""
    width = 150
    box_width = 20
    bar_color = (128, 128, 128)
    bar_thickness = 5
    active_box_color = (128, 128, 255)
    inactive_box_color = (255, 255, 255)
    def __init__(self, label: str, center: tuple[int, int],
                 variable: Variable, scale: tuple[int, int], decimals: int = 0):
        super().__init__()
        self.label = font.render(f"{label}=", True, TEXT_COLOR)
        self.scale = scale
        self.decimals = decimals
        max_text_value = (str(scale[1]) if not self.decimals
                          else str(round(scale[1]*1.0, self.decimals)))
        max_text = font.render(max_text_value, True, TEXT_COLOR)
        self.size = (self.width + self.label.get_width()
                     + font.get_height() + max_text.get_width(), font.get_height())
        self.surf = pygame.Surface(self.size, pygame.SRCALPHA)
        adjusted_center = (center[0] + int(self.size[0]/2), center[1])
        self.rect = self.surf.get_rect(center=adjusted_center, size=self.size)
        self.center = center
        self.variable = variable
        position = ((variable.value-self.scale[0])
                    / (self.scale[1]-self.scale[0])
                    * (self.width-self.box_width))
        self.box_rect = pygame.Rect((position, 0), (self.box_width, font.get_height()))
        self.initial = True

    def update(self, mouse_position: tuple[int, int],
               mouse_down: tuple):
        """Draw the slider and handle interactions."""
        self.surf.fill((0, 0, 0, 0))
        box_color = self.inactive_box_color
        if mouse_down[0] and self.rect.collidepoint(*mouse_down):
            if self.initial:
                self.initial = False
            box_color = self.active_box_color
            self.box_rect.left = self.get_box_position(
                mouse_position[0], self.rect.left, self.width, self.box_width)
        if not self.initial:
            self.variable.value = clamp(
                self.scale[1] * self.box_rect.left / (self.width-self.box_width),
                self.scale[0], self.scale[1]
                )  # type: ignore
            if not self.decimals:
                self.variable.value = int(self.variable.value)  # type: ignore
        pygame.draw.line(self.surf, self.bar_color, (0, self.size[1]/2),
                         (self.width, self.size[1]/2), self.bar_thickness)
        pygame.draw.rect(self.surf, box_color, self.box_rect)
        self.surf.blit(self.label, (self.width + font.get_height()/2, 0))
        value = (int(self.variable.value) if not self.decimals
                 else round(self.variable.value, self.decimals))
        value_text = font.render(str(value), True, TEXT_COLOR)
        self.surf.blit(value_text, (self.width + self.label.get_width() + font.get_height()/2, 0))

    @staticmethod
    @cache
    def get_box_position(mouse_x: int, left: int, width: int, box_width: int):
        """Find the appropriate position for the slider box given the mouse position."""
        return int(
            clamp(int(mouse_x-left-box_width/2), 0, width-box_width)
            )
