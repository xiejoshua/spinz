/**
 * LogFab was previously a floating bottom-right FAB. It has been merged
 * into the center slot of the BottomTabs toolbar so the Log action sits
 * in the natural thumb zone on mobile and reads as part of the chrome
 * rather than as a tacked-on shortcut. This component is kept as an
 * intentional no-op so existing imports compile during the transition.
 */
export function LogFab() {
  return null;
}
