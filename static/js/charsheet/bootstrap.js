import { onReady } from "./utils.js";
import { initTabs } from "./tabs.js";
import { initStandardFloatingWindows } from "./window_manager.js";
import { initLeftTools } from "./left_tools.js";
import { initReputationPanel } from "./reputation_panel.js";
import { initFireflies } from "./fireflies.js";
import { initItemForm } from "./item_form.js?v=20260814a";
import { initSkillSpecModal } from "./skill_spec_modal.js";
import { initTechniqueSpecModal } from "./technique_spec_modal.js";
import { initTraitSpecModal } from "./trait_spec_modal.js";
import { initShopMenu } from "./shop_menu.js?v=20260830a";
import { initLearningMenu } from "./learning_menu.js?v=20260901b";
import { initTooltips } from "./tooltip.js?v=20260902d";
import { initInventoryMenu } from "./inventory_menu.js?v=20260820a";
import { initDamagePanel } from "./damage_panel.js?v=20260801b";
import { initSpellPanel } from "./spell_panel.js";
import { initLessonPanel } from "./lesson_panel.js?v=20260724a";
import { initCharInfoCounter } from "./char_info_counter.js";
import { initSheetActions } from "./sheet_actions.js?v=20260901d";
import { initSchoolsPanel, initWmArcanaFilter } from "./schools_panel.js";
import { initMobileHud } from "./mobile_hud.js";
import { initSkillManager } from "./skill_manager.js";
import { initArmorPanel } from "./armor_panel.js?v=20260820d";
import { initBattleCalculator } from "./battle_calculator.js?v=20260731a";
import { initCarryLoadToggle } from "./carry_load_toggle.js?v=20260827a";
import { initContextRadialMenu } from "./context_radial_menu.js";
import { initRadialMenuGem } from "./radial_menu_gem.js";
import { initCharacterAppearanceModal } from "./character_appearance_modal.js";
import { initCardHand } from "./card_hand.js?v=20260621a";
import { initGodCards } from "./god_card.js?v=20260702a";
import { initCreatureCards } from "./creature_card.js?v=20260802a";
import { initItemTransfers } from "./item_transfers.js?v=20260901a";
import { initItemTransferWindow } from "./item_transfer_window.js?v=20260901a";
import { initTemporaryAttributes } from "./temporary_attributes.js?v=20260731c";
import { initVampirePanel } from "./vampire_panel.js?v=20260802a";
import { initExternalSheetRefresh } from "./external_refresh.js?v=20260901b";

function isRadialMenuEnabled() {
  return document.body?.dataset.radialMenuEnabled === "1";
}

function initCharacterImageEditorSafely() {
  import("./character_image_editor.js?v=20260527c")
    .then(({ initCharacterImageEditor }) => {
      initCharacterImageEditor();
    })
    .catch((_error) => {
      // Keep the rest of the sheet interactive if the optional image editor fails.
    });
}

function runInit(callback) {
  try {
    return callback();
  } catch (_error) {
    return null;
  }
}

function initRadialMenusSafely() {
  if (!isRadialMenuEnabled()) {
    return;
  }
  runInit(initRadialMenuGem);
  runInit(initContextRadialMenu);
}

function initDynamicSheetModules(windowControllers) {
  runInit(initTabs);
  runInit(initCardHand);
  runInit(initShopMenu);
  runInit(initDamagePanel);
  runInit(initTraitSpecModal);
  runInit(() => initLearningMenu({ choiceWindowController: windowControllers?.learnChoice || null }));
  runInit(initSpellPanel);
  runInit(initLessonPanel);
  runInit(initCharInfoCounter);
  runInit(initSchoolsPanel);
  runInit(initWmArcanaFilter);
  runInit(initArmorPanel);
  runInit(initBattleCalculator);
  runInit(initCarryLoadToggle);
  runInit(initCharacterAppearanceModal);
  runInit(initGodCards);
  runInit(initCreatureCards);
  runInit(() => initItemTransfers({ windowController: windowControllers?.itemTransfer || null }));
  runInit(initItemTransferWindow);
  runInit(initVampirePanel);
  runInit(initCharacterImageEditorSafely);
}

onReady(() => {
  let windowControllers = runInit(initStandardFloatingWindows);
  initDynamicSheetModules(windowControllers);
  runInit(initLeftTools);
  runInit(initReputationPanel);
  runInit(initSkillSpecModal);
  runInit(initTechniqueSpecModal);
  runInit(initFireflies);
  runInit(initItemForm);
  runInit(initTooltips);
  runInit(() => initInventoryMenu({
    warningWindowController: windowControllers?.inventoryDeleteWarning || null,
    modifyWindowController: windowControllers?.runeRetrofit || null,
  }));
  runInit(initSheetActions);
  runInit(initSkillManager);
  runInit(initMobileHud);
  runInit(initTemporaryAttributes);
  runInit(initExternalSheetRefresh);
  initRadialMenusSafely();

  document.addEventListener("charsheet:partials-applied", () => {
    windowControllers = runInit(initStandardFloatingWindows);
    initDynamicSheetModules(windowControllers);
    document.dispatchEvent(new Event("learn:refresh-totals"));
  });
});
