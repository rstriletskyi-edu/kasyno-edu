import { Routes } from '@angular/router';
import { Homepage } from './components/homepage/homepage';
import { authGuard } from './guards/auth.guard';

const baseTitle: string = 'Kasyno Edu';

export const routes: Routes = [
  { path: '', redirectTo: 'home', pathMatch: 'full' },
  {
    path: 'home',
    title: baseTitle,
    component: Homepage,
    pathMatch: 'full',
    //canActivate: [authGuard] //blokada przed nieautoryzowanym dostępem
  },
  {
    path: 'dashboard',
    title: `${baseTitle} - Konto`,
    pathMatch: 'full',
    loadComponent: () => import('./components/dashboard/dashboard').then((c) => c.Dashboard),
    canActivate: [authGuard],
  },
  {
    path: 'settings',
    title: `${baseTitle} - Ustawienia`,
    pathMatch: 'full',
    loadComponent: () => import('./components/settings-components/settings/settings').then((c) => c.Settings),
    canActivate: [authGuard],
  },
  {
    path: 'auth',
    children: [
      { path: '', redirectTo: 'login', pathMatch: 'full' },
      {
        path: 'login',
        title: `${baseTitle} - Zaloguj`,
        loadComponent: () =>
          import('./components/auth-components/sign-in/sign-in').then((c) => c.SignIn),
      },
      {
        path: 'register',
        title: `${baseTitle} - Zarejestruj`,
        loadComponent: () =>
          import('./components/auth-components/sign-up/sign-up').then((c) => c.SignUp),
      },
      {
        path: 'password-reset',
        title: `${baseTitle} - Zmień hasło`,
        loadComponent: () =>
          import('./components/auth-components/password-change/password-change').then(
            (c) => c.PasswordChange,
          ),
      },
      {
        path: 'account-activation',
        title: `${baseTitle} - Aktywuj konto`,
        loadComponent: () =>
          import('./components/auth-components/account-activation/account-activation').then(
            (c) => c.AccountActivation,
          ),
      },
    ],
  },
  {
    path: '**',
    loadComponent: () => import('./components/not-found/not-found').then((c) => c.NotFound),
    title: '404 Not Found',
  },
];
