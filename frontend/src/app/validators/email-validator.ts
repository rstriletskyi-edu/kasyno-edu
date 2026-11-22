import { Directive } from '@angular/core';
import {
  AbstractControl,
  NG_VALIDATORS,
  ValidationErrors,
  Validator,
  ValidatorFn,
} from '@angular/forms';

// Any real TLD: letters only (com, pl, museum, ...) or punycode for international ones (xn--p1ai).
const TLD = /^([A-Za-z]{2,63}|xn--[A-Za-z0-9-]{1,59})$/;

/**
 * Complements Angular's built-in `email` validator (which checks the syntax but accepts
 * `user@localhost`): requires a dot in the domain and a valid top-level domain.
 * Returns `{ emailTld: true }`; empty values are left to `required`.
 */
export function emailTldValidator(): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    if (!control.value) {
      return null;
    }

    const value = String(control.value);
    const domain = value.slice(value.lastIndexOf('@') + 1);
    const labels = domain.split('.');
    const valid = value.includes('@') && labels.length >= 2 && TLD.test(labels[labels.length - 1]);
    return valid ? null : { emailTld: true };
  };
}

/** Template-driven adapter: `<input ngModel email emailTld />`. */
@Directive({
  selector: '[emailTld]',
  providers: [{ provide: NG_VALIDATORS, useExisting: EmailTldValidatorDirective, multi: true }],
})
export class EmailTldValidatorDirective implements Validator {
  private readonly validator = emailTldValidator();

  validate(control: AbstractControl): ValidationErrors | null {
    return this.validator(control);
  }
}
