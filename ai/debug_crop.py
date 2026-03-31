import os
import sys
import numpy as np
from PIL import Image

# Add project root to path
sys.path.append(os.getcwd())

from ai.utils.tools import VisualDecoder

def check_image_content(img: Image.Image) -> str:
    """Analyze if image is black, empty, or valid."""
    if not img: return "NONE"
    
    arr = np.array(img)
    mean_color = np.mean(arr)
    std_dev = np.std(arr)
    
    status = []
    if mean_color < 5: status.append("DARK/BLACK")
    elif mean_color > 250: status.append("WHITE/BLANK")
    else: status.append(f"VALID (Mean: {mean_color:.1f})")
    
    if std_dev < 1: status.append("FLAT/SOLID_COLOR")
    
    return ", ".join(status)

def main():
    tiles_dir = "./repo_tiles"
    if not os.path.exists(tiles_dir):
        print(f"❌ Error: {tiles_dir} not found.")
        return

    decoder = VisualDecoder(tiles_dir)
    
    targets = ['src\\components\\footer.tsx::Footer::DEF', 'src\\components\\agenticdev-studio-logo.tsx::AgenticDevStudioLogo::DEF', 'src\\components\\ui\\skeleton.tsx::Skeleton::DEF', '"@/components/ui/tabs"::Tabs::JSX', 'src\\components\\landing\\features.tsx::Features::DEF', 'src\\components\\data-table.tsx::DataTable::DEF', 'src\\components\\ui\\badge.tsx::Badge::DEF', '"@/components/ui/badge"::Badge::JSX', '"@/components/ui/dropdown-menu"::DropdownMenu::JSX', "'react'::ComponentProps", 'src\\components\\landing\\faq.tsx::FAQ::DEF', '"@/components/ui/context-menu"::ContextMenuItem::JSX', '"@/components/ui/scroll-area"::ScrollArea::JSX', 'src\\components\\footer.tsx::GithubButtonFallback::DEF', 'Declaration::component::CALL', 'src\\components\\marketplace-card.tsx::MarketplaceCard::DEF', 'src\\components\\providers.tsx::ThemeProvider::DEF', 'src\\layouts\\NavFooterLayout.tsx::NavFooterLayout::DEF', 'src\\components\\theme-switch.tsx::ThemeSwitch::DEF', 'src\\app\\marketing\\page.tsx::Home::DEF', 'src\\app\\auth\\reset-password\\page.tsx::ResetPasswordPage::DEF', '"@/components/ui/avatar"::Avatar::JSX', 'src\\components\\canvas\\node-rules-dialog.tsx::NodeRulesDialog::DEF', 'Declaration::DropdownMenuRadioItem::CONST', 'src\\components\\team-switcher.tsx::TeamSwitcher::DEF', 'src\\components\\landing\\hero.tsx::TotalUsersButton::DEF', 'src\\components\\credit-system-disabled.tsx::CreditSystemDisabled::DEF', 'src\\components\\landing\\hero.tsx::Hero::DEF', '"@/lib/utils"::cn::CALL', 'src\\app\\layout.tsx::BaseLayout::DEF', 'src\\app\\dashboard\\dashboard\\page.tsx::Page::DEF', 'src\\components\\landing\\hero.tsx::TotalUsersButtonSkeleton::DEF', '"@/components/ui/table"::Table::JSX', 'src\\components\\canvas\\node-context-menu.tsx::NodeContextMenu::DEF', '"@/components/ui/input"::Input::JSX', 'src\\app\\auth\\team-invite\\page.tsx::TeamInvitePage::DEF', '"@/components/ui/button"::Button::JSX', 'src\\components\\ui\\sonner.tsx::Toaster::DEF', '"@/components/workflows/create-workflow-dialog"::CreateWorkflowDialog::JSX', 'src\\components\\ui\\sheet.tsx::Sheet::DEF', 'src\\components\\ui\\breadcrumb.tsx::BreadcrumbEllipsis::DEF', 'Declaration::claims::CALL', 'src\\components\\navigation.tsx::Navigation::DEF', 'src\\components\\ui\\dropdown-menu.tsx::DropdownMenuShortcut::DEF', '"@radix-ui/react-dropdown-menu"::DropdownMenuPrimitive::CALL', '"@/components/credit-system-disabled"::CreditSystemDisabled::JSX', 'src\\components\\purchase-button.tsx::PurchaseButton::DEF', 'src\\components\\teams\\create-team-form.tsx::CreateTeamForm::DEF', 'Declaration::DropdownMenuRadioGroup::CONST', 'src\\app\\settings\\settings\\settings-breadcrumbs.tsx::SettingsBreadcrumbs::DEF', '"motion/react"::motion::CALL', 'src\\app\\auth\\layout.tsx::AuthLayout::DEF', 'src\\components\\footer.tsx::GithubButton::DEF', 'src\\app\\auth\\verify-email\\page.tsx::VerifyEmailPage::DEF', '"@/components/ui/shiny-button"::ShinyButton::JSX', 'src\\components\\canvas\\add-node-dialog.tsx::AddNodeDialog::DEF', '"@/components/separator-with-text"::Separator::JSX', 'Declaration::searchParams::CALL', 'src\\components\\nav-projects.tsx::NavProjects::DEF', 'src\\app\\dashboard\\layout.tsx::DashboardLayout::DEF', 'src\\components\\teams\\invite-member-modal.tsx::InviteMemberModal::DEF', 'src\\components\\page-header.tsx::PageHeader::DEF', 'src\\components\\teams\\remove-member-button.tsx::RemoveMemberButton::DEF', 'src\\components\\separator-with-text.tsx::SeparatorWithText::DEF', 'src\\react-email\\reset-password.tsx::ResetPasswordEmail::DEF', 'src\\components\\ui\\spinner.tsx::Spinner::DEF', 'Declaration::getStackComponentsAction::CONST', 'src\\components\\workflows\\create-workflow-dialog.tsx::CreateWorkflowDialog::DEF', '"@/layouts/NavFooterLayout"::NavFooterLayout::JSX', 'src\\react-email\\team-invite.tsx::TeamInviteEmail::DEF', 'Declaration::stackComponentTable::CONST', 'src\\components\\providers.tsx::RouterChecker::DEF', 'Declaration::DropdownMenuCheckboxItem::CONST']
    
    output_dir = "ai/output/debug_crops"
    os.makedirs(output_dir, exist_ok=True)
    
    # ========== TEST 1: Individual Crops ==========
    print(f"{'='*60}")
    print(f"TEST 1: Individual Crops ({len(targets)} targets)")
    print(f"{'='*60}\n")
    
    for i, family in enumerate(targets):
        print(f"--- Target {i+1}: {family} ---")
        
        # 1. Check raw coords
        norm_fam = decoder._normalize_family(family)
        if norm_fam not in decoder.context.coords:
            print(f"  ❌ Not found in coords (Normalized: {norm_fam})")
            continue
            
        meta = decoder.context.coords[norm_fam]
        print(f"  📍 Tile Index: {meta.get('_tile_index', 'DEFAULT 0')}")
        print(f"     BBox: {meta.get('bbox')}")
        print(f"     Local BBox: {meta.get('_tile_local_bbox', 'Not Set')}")
        
        # 2. Try crop
        crop = decoder.crop_and_decode(family)
        if crop:
            status = check_image_content(crop)
            print(f"  ✅ Crop: {crop.size} - {status}")
            
            save_path = os.path.join(output_dir, f"crop_{i+1}.png")
            crop.save(save_path)
            print(f"     Saved: {save_path}")
        else:
            print(f"  ❌ Crop Failed (returned None)")
            
        print("")
    
    # ========== TEST 2: Stitched Grid ==========
    print(f"{'='*60}")
    print(f"TEST 2: Stitched Grid (bulk_inspect)")
    print(f"{'='*60}\n")
    
    byte_chunks, results = decoder.bulk_inspect(targets)
    
    print(f"  Chunks returned: {len(byte_chunks)}")
    print(f"  Results returned: {len(results)}")
    
    for i, chunk in enumerate(byte_chunks):
        img = Image.open(__import__('io').BytesIO(chunk))
        status = check_image_content(img)
        save_path = os.path.join(output_dir, f"stitched_{i+1}.png")
        img.save(save_path)
        print(f"  Chunk {i+1}: {img.size} - {status}")
        print(f"     Saved: {save_path}")
    
    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
