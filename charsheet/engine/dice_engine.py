from random import randint
from dataclasses import dataclass


@dataclass
class DiceEngine():
    """Simple dice rolling helper for fixed side and roll counts.

    Attributes:
        dice_sides: Number of sides per die.
        dice_rolls: Number of dice to roll.
    """

    dice_sides: int
    dice_rolls: int

    def roll_dice(self) -> list[int]:
        """Roll configured dice and return each single result.

        Returns:
            list[int]: One random result per configured roll.
        """
        return [randint(1, self.dice_sides) for _ in range(self.dice_rolls)]

    def roll(self) -> dict:
        rolls = self.roll_dice()
        return {
            "sides": self.dice_sides,
            "count": self.dice_rolls,
            "rolls": rolls,
            "total": sum(rolls)
        }

    def roll_100(self) -> dict:
        tens = 10 * randint(0, 9)
        ones = randint(1, 10)

        total = tens + ones

        return {
            "sides": 100,
            "count": 1,
            "tens": tens,
            "ones": ones,
            "total": total
        }
