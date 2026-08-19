import {
  readFileSync,
  writeFileSync,
} from 'node:fs';

const [targetPath] = process.argv.slice(2);

if (!targetPath) {
  throw new Error('Usage: node apply-item-all-languages.mjs <item-data.service.ts>');
}

let source = readFileSync(targetPath, 'utf8');

const replacements = [
  {
    description: 'PATCH responses',
    before: '    this.patchData = new PatchDataImpl<Item>(this.linkPath, requestService, rdbService, objectCache, halService, comparator, this.responseMsToLive, this.constructIdEndpoint);',
    after: `    const constructAllLanguagesEndpoint: ConstructIdEndpoint = (endpoint, resourceID) =>
      \`\${this.constructIdEndpoint(endpoint, resourceID)}?projection=allLanguages\`;
    this.patchData = new PatchDataImpl<Item>(this.linkPath, requestService, rdbService, objectCache, halService, comparator, this.responseMsToLive, constructAllLanguagesEndpoint);`,
  },
  {
    description: 'items found by custom URL',
    before: '  public findByCustomUrl(id: string, useCachedVersionIfAvailable = true, reRequestOnStale = true, linksToFollow: FollowLinkConfig<Item>[], projections: string[] = []): Observable<RemoteData<Item>> {',
    after: "  public findByCustomUrl(id: string, useCachedVersionIfAvailable = true, reRequestOnStale = true, linksToFollow: FollowLinkConfig<Item>[], projections: string[] = ['allLanguages']): Observable<RemoteData<Item>> {",
  },
  {
    description: 'items found by UUID',
    before: '    const href$ = this.getIDHrefObs(encodeURIComponent(id), ...linksToFollow);',
    after: `    const href$ = this.getIDHrefObs(encodeURIComponent(id), ...linksToFollow).pipe(
      map((href: string) => \`\${href}\${href.includes('?') ? '&' : '?'}projection=allLanguages\`),
    );`,
  },
];

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
