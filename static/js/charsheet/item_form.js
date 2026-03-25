export function initItemForm() {
  const typeSelect = document.getElementById("shopItemTypeSelect");
  const armorFields = document.getElementById("shopItemArmorFields");
  const weaponFields = document.getElementById("shopItemWeaponFields");
  const shieldFields = document.getElementById("shopItemShieldFields");
  if (!typeSelect || !armorFields || !weaponFields || !shieldFields) {
    return;
  }

  const armorInput = armorFields.querySelector("input[name='armor_rs_total']");
  const stackableRow = document.getElementById("shopItemStackableRow");
  const stackableInput = document.getElementById("shopItemStackableInput");
  const armorModeInputs = armorFields.querySelectorAll("input[name='armor_mode']");
  const armorTotalFields = document.getElementById("shopArmorTotalFields");
  const armorZoneFields = document.getElementById("shopArmorZoneFields");
  const armorZoneInputs = armorFields.querySelectorAll(
    "input[name='armor_rs_head'], input[name='armor_rs_torso'], input[name='armor_rs_arm_left'], input[name='armor_rs_arm_right'], input[name='armor_rs_leg_left'], input[name='armor_rs_leg_right']",
  );
  const weaponDamageAmountInput = weaponFields.querySelector("input[name='weapon_damage_dice_amount']");
  const weaponDamageFacesInput = weaponFields.querySelector("input[name='weapon_damage_dice_faces']");
  const weaponDamageSourceSelect = weaponFields.querySelector("select[name='weapon_damage_source']");
  const weaponMinStInput = weaponFields.querySelector("input[name='weapon_min_st']");
  const weaponWieldModeSelect = document.getElementById("shopWeaponWieldMode");
  const weaponTwoHandFields = document.getElementById("shopWeaponTwoHandFields");
  const weaponH2AmountInput = weaponFields.querySelector("input[name='weapon_h2_dice_amount']");
  const weaponH2FacesInput = weaponFields.querySelector("input[name='weapon_h2_dice_faces']");

  const syncArmorModeFields = () => {
    const selectedModeInput = armorFields.querySelector("input[name='armor_mode']:checked");
    const totalMode = (selectedModeInput ? selectedModeInput.value : "total") === "total";

    armorTotalFields.hidden = !totalMode;
    armorZoneFields.hidden = totalMode;
    if (armorInput) {
      armorInput.required = totalMode;
    }
    armorZoneInputs.forEach((input) => {
      input.required = !totalMode;
    });
  };

  const syncWeaponWieldModeFields = () => {
    const mode = String(weaponWieldModeSelect?.value || "1h");
    const hasTwoHandProfile = mode === "2h" || mode === "vh";
    if (weaponTwoHandFields) {
      weaponTwoHandFields.hidden = !hasTwoHandProfile;
    }
    if (weaponH2AmountInput) {
      weaponH2AmountInput.required = hasTwoHandProfile;
    }
    if (weaponH2FacesInput) {
      weaponH2FacesInput.required = hasTwoHandProfile;
    }
  };

  const syncItemTypeFields = () => {
    const value = String(typeSelect.value || "");
    const isArmor = value === "armor";
    const isWeapon = value === "weapon";
    const isShield = value === "shield";

    armorFields.hidden = !isArmor;
    weaponFields.hidden = !isWeapon;
    shieldFields.hidden = !isShield;

    if (armorInput) {
      armorInput.required = isArmor;
    }
    if (weaponDamageAmountInput) {
      weaponDamageAmountInput.required = isWeapon;
    }
    if (weaponDamageFacesInput) {
      weaponDamageFacesInput.required = isWeapon;
    }
    if (weaponDamageSourceSelect) {
      weaponDamageSourceSelect.required = isWeapon;
    }
    if (weaponMinStInput) {
      weaponMinStInput.required = isWeapon;
    }

    if (stackableRow && stackableInput) {
      const lockStackableOff = isArmor || isWeapon || isShield;
      stackableRow.hidden = lockStackableOff;
      stackableInput.disabled = lockStackableOff;
      if (lockStackableOff) {
        stackableInput.checked = false;
      }
    }

    if (isArmor) {
      syncArmorModeFields();
    } else {
      armorTotalFields.hidden = false;
      armorZoneFields.hidden = true;
      if (armorInput) {
        armorInput.required = false;
      }
      armorZoneInputs.forEach((input) => {
        input.required = false;
      });
    }

    if (isWeapon) {
      syncWeaponWieldModeFields();
    } else if (weaponTwoHandFields) {
      weaponTwoHandFields.hidden = true;
      if (weaponH2AmountInput) {
        weaponH2AmountInput.required = false;
      }
      if (weaponH2FacesInput) {
        weaponH2FacesInput.required = false;
      }
    }
  };

  armorModeInputs.forEach((input) => {
    input.addEventListener("change", syncArmorModeFields);
  });
  weaponWieldModeSelect?.addEventListener("change", syncWeaponWieldModeFields);
  typeSelect.addEventListener("change", syncItemTypeFields);
  stackableInput?.addEventListener("change", syncItemTypeFields);
  syncItemTypeFields();
}
