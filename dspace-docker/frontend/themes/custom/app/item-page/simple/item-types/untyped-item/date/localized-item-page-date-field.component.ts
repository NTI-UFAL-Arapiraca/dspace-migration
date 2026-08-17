import { AsyncPipe } from '@angular/common';
import {
  Component,
  Input,
} from '@angular/core';
import { LocaleService } from '@dspace/core/locale/locale.service';
import { Item } from '@dspace/core/shared/item.model';
import { MetadataValue } from '@dspace/core/shared/metadata.models';
import {
  BehaviorSubject,
  combineLatest,
  map,
  Observable,
} from 'rxjs';

import { MetadataValuesComponent } from '../../../../../../../../app/item-page/field-components/metadata-values/metadata-values.component';

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/;
const ISO_YEAR_MONTH = /^(\d{4})-(\d{2})$/;

function isValidMonth(month: number): boolean {
  return month >= 1 && month <= 12;
}

function isValidDate(year: number, month: number, day: number): boolean {
  if (!isValidMonth(month) || day < 1) {
    return false;
  }

  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysPerMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day <= daysPerMonth[month - 1];
}

/**
 * Format an ISO date using Brazilian numeric order only for the pt-BR locale.
 * Values with unknown precision or invalid calendar dates are kept verbatim.
 */
export function formatIssuedDate(value: string, language: string): string {
  const normalizedLanguage = language?.replace('_', '-').toLowerCase();
  if (normalizedLanguage !== 'pt-br') {
    return value;
  }

  const dateMatch = ISO_DATE.exec(value);
  if (dateMatch) {
    const [, year, month, day] = dateMatch;
    if (isValidDate(Number(year), Number(month), Number(day))) {
      return `${day}/${month}/${year}`;
    }
    return value;
  }

  const yearMonthMatch = ISO_YEAR_MONTH.exec(value);
  if (yearMonthMatch) {
    const [, year, month] = yearMonthMatch;
    return isValidMonth(Number(month)) ? `${month}/${year}` : value;
  }

  return value;
}

@Component({
  selector: 'ds-item-page-date-field',
  templateUrl: './localized-item-page-date-field.component.html',
  imports: [
    AsyncPipe,
    MetadataValuesComponent,
  ],
})
export class LocalizedItemPageDateFieldComponent {

  private readonly item$ = new BehaviorSubject<Item | undefined>(undefined);

  readonly separator = ', ';
  readonly label = 'item.page.date';
  readonly dateValues$: Observable<MetadataValue[]>;

  @Input() set item(item: Item | undefined) {
    this.item$.next(item);
  }

  constructor(localeService: LocaleService) {
    this.dateValues$ = combineLatest([
      this.item$,
      localeService.getCurrentLanguageCode(),
    ]).pipe(
      map(([item, language]) => (item?.allMetadata(['dc.date.issued']) ?? []).map(
        (metadata) => ({
          ...metadata,
          value: formatIssuedDate(metadata.value, language),
        }),
      )),
    );
  }
}
