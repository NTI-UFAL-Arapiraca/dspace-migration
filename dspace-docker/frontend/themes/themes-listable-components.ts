import { LISTABLE_COMPONENTS as CUSTOM_LISTABLE_COMPONENTS } from './custom/lazy-listable-components';
import { LISTABLE_COMPONENTS as DSPACE_LISTABLE_COMPONENTS } from './dspace/lazy-listable-components';

/**
 * Bundle listable components from every enabled theme so themed standalone
 * item pages are available to the component loader.
 */
export const THEME_LISTABLE_COMPONENTS = [
  ...CUSTOM_LISTABLE_COMPONENTS,
  ...DSPACE_LISTABLE_COMPONENTS,
];
