import { inject } from '@angular/core';
import {
  ActivatedRouteSnapshot,
  ResolveFn,
} from '@angular/router';
import { ItemDataService } from '@dspace/core/data/item-data.service';
import { RemoteData } from '@dspace/core/data/remote-data';
import { Item } from '@dspace/core/shared/item.model';
import { getFirstCompletedRemoteData } from '@dspace/core/shared/operators';
import { Observable } from 'rxjs';

/**
 * Reload an item with every metadata language exclusively inside the
 * administrative edit area. Public item and search requests remain filtered
 * by the locale negotiated with the REST backend.
 */
export const editItemAllLanguagesResolver: ResolveFn<RemoteData<Item>> = (
  route: ActivatedRouteSnapshot,
): Observable<RemoteData<Item>> | RemoteData<Item> => {
  const itemService = inject(ItemDataService);
  const parentItem = route.parent?.data?.dso as RemoteData<Item>;
  const selfHref = parentItem?.payload?._links?.self?.href;

  if (!selfHref) {
    return parentItem;
  }

  const separator = selfHref.includes('?') ? '&' : '?';
  return itemService.findByHref(
    `${selfHref}${separator}projection=allLanguages`,
    false,
    true,
  ).pipe(getFirstCompletedRemoteData());
};
