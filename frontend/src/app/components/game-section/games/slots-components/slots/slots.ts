import { Component, OnInit, inject, signal } from '@angular/core';
import { SlotsClient } from '../../../../../services/games-clients/slots-client';

@Component({
  imports: [],
  selector: 'slots',
  styleUrl: './slots.css',
  templateUrl: './slots.html',
})
export class Slots implements OnInit {

  private readonly client = inject(SlotsClient);

  ngOnInit() {

  }

}
