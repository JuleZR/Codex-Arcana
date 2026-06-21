import { onReady } from "./utils.js";
import { initTabs } from "./tabs.js";
import { initStandardFloatingWindows } from "./window_manager.js";
import { initLeftTools } from "./left_tools.js";
import { initReputationPanel } from "./reputation_panel.js";
import { initFireflies } from "./fireflies.js";
import { initItemForm } from "./item_form.js";
import { initSkillSpecModal } from "./skill_spec_modal.js";
import { initTechniqueSpecModal } from "./technique_spec_modal.js";
import { initShopMenu } from "./shop_menu.js";
import { initLearningMenu } from "./learning_menu.js?v=20260608a";
import { initTooltips } from "./tooltip.js";
import { initWalletTooltip } from "./wallet_tooltip.js";
import { initInventoryMenu } from "./inventory_menu.js";
import { initDamagePanel } from "./damage_panel.js";
import { initSpellPanel } from "./spell_panel.js";
import { initCharInfoCounter } from "./char_info_counter.js";
import { initSheetActions } from "./sheet_actions.js?v=20260608a";
import { initSchoolsPanel, initWmArcanaFilter } from "./schools_panel.js";
import { initMobileHud } from "./mobile_hud.js";
import { initSkillManager } from "./skill_manager.js";
import { initArmorPanel } from "./armor_panel.js";
import { initBattleCalculator } from "./battle_calculator.js";
import { initCarryLoadToggle } from "./carry_load_toggle.js";
import { initContextRadialMenu } from "./context_radial_menu.js";
import { initRadialMenuGem } from "./radial_menu_gem.js";
import { initCharacterAppearanceModal } from "./character_appearance_modal.js";
import { initCardHand } from "./card_hand.js?v=20260621a";
import { initGodCards } from "./god_card.js?v=20260621a";
import { initCreatureCards } from "./creature_card.js?v=20260621b";

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

onReady(() => {
  initTabs();
  const windowControllers = initStandardFloatingWindows();
  initLeftTools();
  initReputationPanel();
  initSkillSpecModal();
  initTechniqueSpecModal();
  initFireflies();
  initItemForm();
  initShopMenu();
  initLearningMenu({ choiceWindowController: windowControllers?.learnChoice || null });
  initTooltips();
  initWalletTooltip();
  initInventoryMenu({
    warningWindowController: windowControllers?.inventoryDeleteWarning || null,
    modifyWindowController: windowControllers?.runeRetrofit || null,
  });
  initSheetActions();
  initSkillManager();
  initDamagePanel();
  initSpellPanel();
  initCharInfoCounter();
  initSchoolsPanel();
  initWmArcanaFilter();
  initArmorPanel();
  initBattleCalculator();
  initCarryLoadToggle();
  initCharacterAppearanceModal();
  initCardHand();
  initGodCards();
  initCreatureCards();
  initMobileHud();
  initCharacterImageEditorSafely();
  if (isRadialMenuEnabled()) {
    try {
      initRadialMenuGem();
    } catch (_error) {
      // Keep the rest of the sheet interactive if the decorative gem fails.
    }
    initContextRadialMenu();
  }

  document.addEventListener("charsheet:partials-applied", () => {
    initTabs();
    initStandardFloatingWindows();
    initDamagePanel();
    initLearningMenu({ choiceWindowController: windowControllers?.learnChoice || null });
    initSpellPanel();
    initCharInfoCounter();
    initSchoolsPanel();
    initWmArcanaFilter();
    initArmorPanel();
    initBattleCalculator();
    initCarryLoadToggle();
    initCharacterAppearanceModal();
    initCardHand();
    initGodCards();
    initCreatureCards();
    document.dispatchEvent(new Event("learn:refresh-totals"));
    initCharacterImageEditorSafely();
  });
});
