import fs from 'node:fs';

const [localeServicePath] = process.argv.slice(2);

if (!localeServicePath) {
  throw new Error('Uso: node apply-default-anonymous-language.mjs <locale.service.ts>');
}

const source = fs.readFileSync(localeServicePath, 'utf8');
const browserLanguageSelection = `      // Attempt to get the browser language from the user
      return this.getLanguageCodeList()
        .pipe(
          map(browserLangs => {
            return browserLangs
              .map(browserLang => browserLang.split(';')[0])
              .find(browserLang =>
                this.translate.getLangs().some(userLang => userLang.toLowerCase() === browserLang.toLowerCase()),
              ) || this.appConfig.fallbackLanguage;
          }),
        );`;
const configuredDefaultSelection = `      // With no explicit UI preference, start from the repository default.
      // Browser Accept-Language must not override the site's default locale.
      return of(this.appConfig.fallbackLanguage);`;

const occurrences = source.split(browserLanguageSelection).length - 1;
if (occurrences !== 1) {
  throw new Error(
    `Esperado exatamente um seletor de idioma do navegador em ${localeServicePath}; encontrado(s): ${occurrences}`,
  );
}

fs.writeFileSync(
  localeServicePath,
  source.replace(browserLanguageSelection, configuredDefaultSelection),
);
