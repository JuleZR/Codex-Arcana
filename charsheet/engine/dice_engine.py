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
        rolls: list[int] = []
        for _ in range(self.dice_rolls):
            rolls.append(randint(1, self.dice_sides))
        
        return rolls
    
    def roll_sum(self) -> int:
        """Return the summed total of one full dice roll sequence.

        Returns:
            int: Sum of all values returned by ``roll_dice()``.
        """
        return sum/(self.roll_dice())
