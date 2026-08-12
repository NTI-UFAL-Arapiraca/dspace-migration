import { Component } from '@angular/core';

import { HomeNewsComponent as BaseComponent } from '../../../../../app/home-page/home-news/home-news.component';

/**
 * Suppress the stock DSpace promotional banner on the home page.
 *
 * The component remains registered in the custom theme so the upstream home
 * page does not need to be copied and maintained locally.
 */
@Component({
  selector: 'ds-themed-home-news',
  template: '',
})
export class HomeNewsComponent extends BaseComponent {
}
