import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

export function strictEmailValidator(): ValidatorFn {
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

  return (control: AbstractControl): ValidationErrors | null => {
    if (!control.value) {
      return null;
    }

    const isValid = emailRegex.test(control.value);
    return isValid ? null : { strictEmail: true };
  };
}
