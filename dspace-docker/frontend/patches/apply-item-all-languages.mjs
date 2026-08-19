import {
  readFileSync,
  writeFileSync,
} from 'node:fs';

const [itemDataPath, editRoutesPath] = process.argv.slice(2);

if (!itemDataPath || !editRoutesPath) {
  throw new Error(
    'Usage: node apply-item-all-languages.mjs <item-data.service.ts> <edit-item-page-routes.ts>',
  );
}

const itemDataReplacements = [
  {
    description: 'PATCH responses',
    before: '    this.patchData = new PatchDataImpl<Item>(this.linkPath, requestService, rdbService, objectCache, halService, comparator, this.responseMsToLive, this.constructIdEndpoint);',
    after: `    const constructAllLanguagesEndpoint: ConstructIdEndpoint = (endpoint, resourceID) =>
      \`\${this.constructIdEndpoint(endpoint, resourceID)}?projection=allLanguages\`;
    this.patchData = new PatchDataImpl<Item>(this.linkPath, requestService, rdbService, objectCache, halService, comparator, this.responseMsToLive, constructAllLanguagesEndpoint);`,
  },
];

const editRoutesReplacements = [
  {
    description: 'administrative item resolver import',
    before: "import { i18nBreadcrumbResolver } from '@dspace/core/breadcrumbs/i18n-breadcrumb.resolver';",
    after: `import { i18nBreadcrumbResolver } from '@dspace/core/breadcrumbs/i18n-breadcrumb.resolver';

import { editItemAllLanguagesResolver } from './edit-item-all-languages.resolver';`,
  },
  {
    description: 'administrative item resolver registration',
    before: `    resolve: {
      breadcrumb: i18nBreadcrumbResolver,
    },`,
    after: `    resolve: {
      breadcrumb: i18nBreadcrumbResolver,
      dso: editItemAllLanguagesResolver,
    },`,
  },
];

function applyReplacements(targetPath, replacements) {
  let source = readFileSync(targetPath, 'utf8');
  for (const replacement of replacements) {
    const occurrences = source.split(replacement.before).length - 1;
    if (occurrences !== 1) {
      throw new Error(
        `Expected exactly one DSpace 10.x source location for ${replacement.description}, found ${occurrences}. ` +
        'Review the patch before using a newer upstream image.',
      );
    }
    source = source.replace(replacement.before, replacement.after);
  }
  writeFileSync(targetPath, source, 'utf8');
}

applyReplacements(itemDataPath, itemDataReplacements);
applyReplacements(editRoutesPath, editRoutesReplacements);
