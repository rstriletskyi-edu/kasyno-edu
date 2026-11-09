import { Routes } from '@angular/router';
import { Homepage } from './components/homepage/homepage';

const baseTitle: string = 'Kasyno Edu';

export const routes: Routes = [
  { path: '', redirectTo: 'home', pathMatch: 'full'},
  {
    path: 'home',
    title: baseTitle,
    component: Homepage,
    pathMatch: 'full',
    //canActivate: [authGuard] //blokada przed nieautoryzowanym dostępem
  },
  {
    path: 'dashboard',
    title: `${baseTitle} - Account`,
    pathMatch: 'full',
    loadComponent: () => import('./components/dashboard/dashboard').then(c => c.Dashboard),
    //canActivate: [authGuard]
  },
  {
    path: 'auth',
    children: [
      { path: '', redirectTo: 'login', pathMatch: 'full' },
      {
        path: 'login',
        title: `${baseTitle} - Sign In`,
        loadComponent: () => import('./components/auth-components/sign-in/sign-in').then(c => c.SignIn) //lazy loading komponentu
      },
      {
        path: 'register',
        title: `${baseTitle} - Sign Up`,
        loadComponent: () => import('./components/auth-components/sign-up/sign-up').then(c => c.SignUp)
      },
      {
        path: 'password-reset',
        title: `${baseTitle} - Change Password`,
        loadComponent: () => import('./components/auth-components/password-change/password-change').then(c => c.PasswordChange)
      },
      {
        path: 'account-activation',
        title: `${baseTitle} - Activcate Account`,
        loadComponent: () => import('./components/auth-components/account-activation/account-activation').then(c => c.AccountActivation)
      },
    ]
  },
  {
    path: '**',
    loadComponent: () => import('./components/not-found/not-found').then(c => c.NotFound),
    title: '404 Not Found'
  },
];
