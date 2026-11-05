// L'établi de l'accueil : une Arduino Uno qui fait courir trois LED (chenillard), sur une plaque à
// trous au pas de 2,54 mm. Dessins des éléments Wokwi (licence MIT, @wokwi/elements).
import { useEffect, useState } from 'react';
import '@wokwi/elements/dist/esm/arduino-uno-element.js';
import '@wokwi/elements/dist/esm/led-element.js';
import '@wokwi/elements/dist/esm/resistor-element.js';

const CHANNELS = [
  ['D2', 'red', 'rouge'],
  ['D3', 'yellow', 'jaune'],
  ['D4', 'limegreen', 'verte'],
];

function useChenillard(period = 420) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (still) return undefined;
    const t = setInterval(() => setStep((s) => (s + 1) % CHANNELS.length), period);
    return () => clearInterval(t);
  }, [period]);
  return step;
}

export default function Bench() {
  const step = useChenillard();
  return (
    <figure className="bench">
      {/* Illustration : ni lue ni atteignable au clavier (les éléments Wokwi sont focalisables). */}
      <div className="bench-plate" aria-hidden="true" inert>
        <div className="bench-uno">
          <wokwi-arduino-uno ledPower="true" led13={step === 0 ? 'true' : undefined} />
        </div>
        <div className="bench-row">
          {CHANNELS.map(([pin, color], i) => (
            <div className="bench-ch" key={pin}>
              <wokwi-led color={color} value={step === i ? 'true' : undefined} />
              <wokwi-resistor value="220" />
              <code>{pin}</code>
            </div>
          ))}
        </div>
      </div>
      <figcaption>
        <span><b>Chenillard</b> : trois LED sur D2, D3 et D4</span>
        <span>résistance série de 220 Ω calculée par le moteur</span>
      </figcaption>
    </figure>
  );
}
