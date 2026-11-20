import { __decorate } from "tslib";
import { Injectable } from '@angular/core';
import { FirebaseError, getApp, getApps, initializeApp } from 'firebase/app';
import { FacebookAuthProvider, GoogleAuthProvider, createUserWithEmailAndPassword, getAuth, onAuthStateChanged, reload, sendEmailVerification, sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup, signOut, } from 'firebase/auth';
import { environment } from '../../environments/environment';
let FirebaseAuthService = class FirebaseAuthService {
    get isConfigured() {
        const { apiKey, authDomain, projectId, appId } = environment.firebase;
        return Boolean(apiKey && authDomain && projectId && appId);
    }
    async signIn(email, password) {
        const result = await signInWithEmailAndPassword(this.auth, email, password);
        return result.user;
    }
    async signInWithGoogle() {
        const provider = new GoogleAuthProvider();
        const result = await signInWithPopup(this.auth, provider);
        return result.user;
    }
    async signInWithFacebook() {
        const provider = new FacebookAuthProvider();
        const result = await signInWithPopup(this.auth, provider);
        return result.user;
    }
    async signUp(email, password) {
        const result = await createUserWithEmailAndPassword(this.auth, email, password);
        await sendEmailVerification(result.user);
        return result.user;
    }
    sendVerificationEmail(user) {
        return sendEmailVerification(user);
    }
    async refreshUser(user) {
        await reload(user);
        if (user.emailVerified)
            await user.getIdToken(true);
        return user;
    }
    async getIdToken() {
        if (!this.isConfigured)
            return null;
        const user = await this.getCurrentUser();
        return user ? user.getIdToken() : null;
    }
    sendPasswordReset(email) {
        return sendPasswordResetEmail(this.auth, email);
    }
    signOut() {
        return signOut(this.auth);
    }
    getCurrentUser() {
        return new Promise((resolve, reject) => {
            let unsubscribe = () => { };
            unsubscribe = onAuthStateChanged(this.auth, (user) => {
                unsubscribe();
                resolve(user);
            }, (error) => {
                unsubscribe();
                reject(error);
            });
        });
    }
    get auth() {
        if (!this.isConfigured) {
            throw new Error('Firebase nie jest skonfigurowany. Uzupełnij dane w pliku environment.');
        }
        const app = getApps().some((candidate) => candidate.name === 'kasyno-edu')
            ? getApp('kasyno-edu')
            : initializeApp(environment.firebase, 'kasyno-edu');
        return getAuth(app);
    }
};
FirebaseAuthService = __decorate([
    Injectable({ providedIn: 'root' })
], FirebaseAuthService);
export { FirebaseAuthService };
export function firebaseErrorMessage(error) {
    if (error instanceof FirebaseError) {
        switch (error.code) {
            case 'auth/invalid-credential':
            case 'auth/wrong-password':
            case 'auth/user-not-found':
                return 'Nieprawidłowy e-mail lub hasło.';
            case 'auth/email-already-in-use':
                return 'Konto z tym adresem e-mail już istnieje.';
            case 'auth/weak-password':
                return 'Hasło jest za słabe. Użyj co najmniej 6 znaków.';
            case 'auth/invalid-email':
                return 'Podaj prawidłowy adres e-mail.';
            case 'auth/popup-closed-by-user':
                return 'Logowanie zostało anulowane (zamknięto okno).';
            case 'auth/cancelled-popup-request':
                return 'Przerwano poprzednie żądanie logowania.';
            case 'auth/popup-blocked':
                return 'Wyskakujące okienko logowania zostało zablokowane przez przeglądarkę.';
            case 'auth/account-exists-with-different-credential':
                return 'Konto z tym adresem e-mail już istnieje przy użyciu innego dostawcy.';
            case 'auth/too-many-requests':
                return 'Zbyt wiele prób. Spróbuj ponownie za chwilę.';
            case 'auth/network-request-failed':
                return 'Brak połączenia z Firebase. Sprawdź połączenie z internetem.';
            default:
                return `Nie udało się wykonać operacji Firebase (${error.code}).`;
        }
    }
    return error instanceof Error ? error.message : 'Wystąpił nieoczekiwany błąd.';
}
