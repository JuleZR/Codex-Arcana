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
import { initLearningMenu } from "./learning_menu.js";
import { initTooltips } from "./tooltip.js";
import { initWalletTooltip } from "./wallet_tooltip.js";
import { initInventoryMenu } from "./inventory_menu.js";
import { initDamagePanel } from "./damage_panel.js";
import { initCharInfoCounter } from "./char_info_counter.js";
import { initSheetActions } from "./sheet_actions.js";
import { initSchoolsPanel } from "./schools_panel.js";

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
  initInventoryMenu({ warningWindowController: windowControllers?.inventoryDeleteWarning || null });
  initSheetActions();
  initDamagePanel();
  initCharInfoCounter();
  initSchoolsPanel();

  document.addEventListener("charsheet:partials-applied", () => {
    initStandardFloatingWindows();
    initDamagePanel();
    initCharInfoCounter();
    initSchoolsPanel();
    document.dispatchEvent(new Event("learn:refresh-totals"));
  });
});
