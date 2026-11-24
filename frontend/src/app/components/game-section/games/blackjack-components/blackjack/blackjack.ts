import { Component, OnInit, inject, signal } from '@angular/core';
import { BlackjackClient } from '../../../../../services/games-clients/blackjack-client';

@Component({
  imports: [],
  selector: 'blackjack',
  styleUrl: './blackjack.css',
  templateUrl: './blackjack.html',
})
export class Blackjack implements OnInit {

  private readonly client = inject(BlackjackClient);

  ngOnInit() {

  }

}
