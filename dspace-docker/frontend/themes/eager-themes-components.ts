import { COMPONENTS as CUSTOM_THEME_EAGER_COMPONENTS } from './custom/eager-theme-components';
import { COMPONENTS as DSPACE_THEME_EAGER_COMPONENTS } from './dspace/eager-theme-components';

/**
 * Bundle eager components from every enabled theme so their decorators are
 * registered when the application starts.
 */
export const EAGER_THEME_COMPONENTS = [
  ...CUSTOM_THEME_EAGER_COMPONENTS,
  ...DSPACE_THEME_EAGER_COMPONENTS,
];
