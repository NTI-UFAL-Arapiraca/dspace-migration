import { AsyncPipe } from '@angular/common';
import {
  Component,
  inject,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '@dspace/core/auth/auth.service';
import { LocaleService } from '@dspace/core/locale/locale.service';
import { isEmpty } from '@dspace/shared/utils/empty.util';
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap';
import { TranslateModule } from '@ngx-translate/core';
import {
  combineLatest,
  filter,
  take,
} from 'rxjs';
import { ThemedLangSwitchComponent } from 'src/app/shared/lang-switch/themed-lang-switch.component';

import { ContextHelpToggleComponent } from '../../../../app/header/context-help-toggle/context-help-toggle.component';
import { HeaderComponent as BaseComponent } from '../../../../app/header/header.component';
import { ThemedSearchNavbarComponent } from '../../../../app/search-navbar/themed-search-navbar.component';
import { ThemedAuthNavMenuComponent } from '../../../../app/shared/auth-nav-menu/themed-auth-nav-menu.component';
import { ImpersonateNavbarComponent } from '../../../../app/shared/impersonate-navbar/impersonate-navbar.component';

const DEFAULT_ANONYMOUS_LANGUAGE = 'pt-BR';

@Component({
  selector: 'ds-themed-header',
  styleUrls: ['../../../../app/header/header.component.scss'],
  templateUrl: '../../../../app/header/header.component.html',
  imports: [
    AsyncPipe,
    ContextHelpToggleComponent,
    ImpersonateNavbarComponent,
    NgbDropdownModule,
    RouterLink,
    ThemedAuthNavMenuComponent,
    ThemedLangSwitchComponent,
    ThemedSearchNavbarComponent,
    TranslateModule,
  ],
})
export class HeaderComponent extends BaseComponent {

  private readonly localeService = inject(LocaleService);
  private readonly authService = inject(AuthService);

  override ngOnInit(): void {
    super.ngOnInit();

    // An explicit language selection always wins. When there is no cookie,
    // wait for authentication to settle so an EPerson language preference is
    // not overwritten by the public site's default.
    if (isEmpty(this.localeService.getLanguageCodeFromCookie())) {
      combineLatest([
        this.authService.isAuthenticated(),
        this.authService.isAuthenticationLoaded(),
      ]).pipe(
        filter(([, authenticationLoaded]) => authenticationLoaded),
        take(1),
      ).subscribe(([authenticated]) => {
        if (!authenticated && isEmpty(this.localeService.getLanguageCodeFromCookie())) {
          this.localeService.setCurrentLanguageCode(DEFAULT_ANONYMOUS_LANGUAGE);
        }
      });
    }
  }
}
