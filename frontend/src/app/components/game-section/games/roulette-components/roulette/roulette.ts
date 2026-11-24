import { Component, OnInit, inject, signal } from '@angular/core';
import { RouletteClient } from '../../../../../services/games-clients/roulette-client';

@Component({
  imports: [],
  selector: 'roulette',
  styleUrl: './roulette.css',
  templateUrl: './roulette.html',
})
export class Roulette implements OnInit {
  
  private readonly client = inject(RouletteClient);
  
  ngOnInit() {

  }

}
