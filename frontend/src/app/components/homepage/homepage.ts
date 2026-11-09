import { Component, signal } from '@angular/core';
import { GameSection } from '../game-section/game-section';
import { LearningSection } from '../learning-section/learning-section';

@Component({
  imports: [GameSection, LearningSection],
  selector: 'homepage',
  styleUrl: './homepage.css',
  templateUrl: './homepage.html',
})
export class Homepage {}
