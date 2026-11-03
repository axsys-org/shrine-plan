// Input validation - only allow alphanumeric, spaces, commas, and periods
// This prevents SQL injection and other attacks
export function validatePhrase(phrase) {
    if (!phrase || phrase.trim().length === 0) {
        return { valid: false, error: 'Phrase cannot be empty' };
    }
    // Allow: a-z, A-Z, 0-9, spaces, commas, periods
    // Block: special chars, quotes, semicolons, etc.
    const allowedPattern = /^[a-zA-Z0-9\s,.]+$/;
    if (!allowedPattern.test(phrase)) {
        return {
            valid: false,
            error: 'Only letters, numbers, spaces, commas, and periods are allowed'
        };
    }
    // Additional security: check for common SQL injection patterns
    // Note: SQL keywords like CREATE/SELECT etc are NOT blocked — they're common English words
    // and parameterized queries already prevent injection.
    const dangerousPatterns = [
        /(\-\-|\/\*|\*\/)/, /* SQL comments */
        /['";`]/, /* Quote characters */
        /(\.\.\/|\\)/, /* Path traversal */
    ];
    for (const pattern of dangerousPatterns) {
        if (pattern.test(phrase)) {
            return {
                valid: false,
                error: 'Invalid characters detected'
            };
        }
    }
    // Check length
    if (phrase.length > 100) {
        return { valid: false, error: 'Phrase too long (max 100 characters)' };
    }
    return { valid: true };
}
// Alphanumeric Qabbala: 0-9 = 0-9, a=10, b=11... z=35
const alphanumericQabbalaMap = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'a': 10, 'b': 11, 'c': 12, 'd': 13, 'e': 14, 'f': 15, 'g': 16, 'h': 17,
    'i': 18, 'j': 19, 'k': 20, 'l': 21, 'm': 22, 'n': 23, 'o': 24, 'p': 25,
    'q': 26, 'r': 27, 's': 28, 't': 29, 'u': 30, 'v': 31, 'w': 32, 'x': 33, 'y': 34, 'z': 35,
};
// Numeric QWERTY: 1-9 = 0-8, 0=9, q=10, w=11... m=35
const numericQwertyMap = {
    '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8, '0': 9,
    'q': 10, 'w': 11, 'e': 12, 'r': 13, 't': 14, 'y': 15, 'u': 16, 'i': 17,
    'o': 18, 'p': 19, 'a': 20, 's': 21, 'd': 22, 'f': 23, 'g': 24, 'h': 25,
    'j': 26, 'k': 27, 'l': 28, 'z': 29, 'x': 30, 'c': 31, 'v': 32, 'b': 33, 'n': 34, 'm': 35,
};
// Ordinal: a=1, b=2... z=26, 0-9=0-9
const ordinalMap = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8,
    'i': 9, 'j': 10, 'k': 11, 'l': 12, 'm': 13,
    'n': 14, 'o': 15, 'p': 16, 'q': 17, 'r': 18, 's': 19, 't': 20,
    'u': 21, 'v': 22, 'w': 23, 'x': 24, 'y': 25, 'z': 26,
};
// QWERTY: q=1, w=2... m=26, 0-9=0-9
const qwertyMap = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'q': 1, 'w': 2, 'e': 3, 'r': 4, 't': 5, 'y': 6, 'u': 7, 'i': 8,
    'o': 9, 'p': 10, 'a': 11, 's': 12, 'd': 13,
    'f': 14, 'g': 15, 'h': 16, 'j': 17, 'k': 18, 'l': 19,
    'z': 20, 'x': 21, 'c': 22, 'v': 23, 'b': 24, 'n': 25, 'm': 26,
};
// Synx: 0-9 = 1,2,3,4,5,6,7,9,10,12, a=14, b=15... z=1260
const synxMap = {
    '0': 1, '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 9, '8': 10, '9': 12,
    'a': 14, 'b': 15, 'c': 18, 'd': 20, 'e': 21, 'f': 28, 'g': 30, 'h': 35,
    'i': 36, 'j': 42, 'k': 45, 'l': 60, 'm': 63, 'n': 70, 'o': 84, 'p': 90,
    'q': 105, 'r': 126, 's': 140, 't': 180, 'u': 210, 'v': 252, 'w': 315, 'x': 420, 'y': 630, 'z': 1260,
};
// Alphanumeric Squares: 0-9 = squares 0-81, a=100, b=121... z=1225
const alphanumericSquaresMap = {
    '0': 0, '1': 1, '2': 4, '3': 9, '4': 16, '5': 25, '6': 36, '7': 49, '8': 64, '9': 81,
    'a': 100, 'b': 121, 'c': 144, 'd': 169, 'e': 196, 'f': 225, 'g': 256, 'h': 289,
    'i': 324, 'j': 361, 'k': 400, 'l': 441, 'm': 484, 'n': 529, 'o': 576, 'p': 625,
    'q': 676, 'r': 729, 's': 784, 't': 841, 'u': 900, 'v': 961, 'w': 1024, 'x': 1089, 'y': 1156, 'z': 1225,
};
// Alphanumeric Primes: 0-9 = primes 1,2,3,5,7,11,13,17,19,23, a=29, b=31... z=149
const alphanumericPrimesMap = {
    '0': 1, '1': 2, '2': 3, '3': 5, '4': 7, '5': 11, '6': 13, '7': 17, '8': 19, '9': 23,
    'a': 29, 'b': 31, 'c': 37, 'd': 41, 'e': 43, 'f': 47, 'g': 53, 'h': 59,
    'i': 61, 'j': 67, 'k': 71, 'l': 73, 'm': 79, 'n': 83, 'o': 89, 'p': 97,
    'q': 101, 'r': 103, 's': 107, 't': 109, 'u': 113, 'v': 127, 'w': 131, 'x': 137, 'y': 139, 'z': 149,
};
// Alphanumeric Trigonal: 0-9 = triangular numbers 0,1,3,6,10,15,21,28,36,45, a=55, b=66... z=630
const alphanumericTrigonalMap = {
    '0': 0, '1': 1, '2': 3, '3': 6, '4': 10, '5': 15, '6': 21, '7': 28, '8': 36, '9': 45,
    'a': 55, 'b': 66, 'c': 78, 'd': 91, 'e': 105, 'f': 120, 'g': 136, 'h': 153,
    'i': 171, 'j': 190, 'k': 210, 'l': 231, 'm': 253, 'n': 276, 'o': 300, 'p': 325,
    'q': 351, 'r': 378, 's': 406, 't': 435, 'u': 465, 'v': 496, 'w': 528, 'x': 561, 'y': 595, 'z': 630,
};
// Numeric QWERTY Squares: same layout as Numeric QWERTY but with square values
const numericQwertySquaresMap = {
    '1': 0, '2': 1, '3': 4, '4': 9, '5': 16, '6': 25, '7': 36, '8': 49, '9': 64, '0': 81,
    'q': 100, 'w': 121, 'e': 144, 'r': 169, 't': 196, 'y': 225, 'u': 256, 'i': 289,
    'o': 324, 'p': 361, 'a': 400, 's': 441, 'd': 484, 'f': 529, 'g': 576, 'h': 625,
    'j': 676, 'k': 729, 'l': 784, 'z': 841, 'x': 900, 'c': 961, 'v': 1024, 'b': 1089, 'n': 1156, 'm': 1225,
};
// Numeric QWERTY Primes: same layout as Numeric QWERTY but with prime values
const numericQwertyPrimesMap = {
    '1': 1, '2': 2, '3': 3, '4': 5, '5': 7, '6': 11, '7': 13, '8': 17, '9': 19, '0': 23,
    'q': 29, 'w': 31, 'e': 37, 'r': 41, 't': 43, 'y': 47, 'u': 53, 'i': 59,
    'o': 61, 'p': 67, 'a': 71, 's': 73, 'd': 79, 'f': 83, 'g': 89, 'h': 97,
    'j': 101, 'k': 103, 'l': 107, 'z': 109, 'x': 113, 'c': 127, 'v': 131, 'b': 137, 'n': 139, 'm': 149,
};
// Numeric QWERTY Trigonal: same layout as Numeric QWERTY but with triangular values
const numericQwertyTrigonalMap = {
    '1': 0, '2': 1, '3': 3, '4': 6, '5': 10, '6': 15, '7': 21, '8': 28, '9': 36, '0': 45,
    'q': 55, 'w': 66, 'e': 78, 'r': 91, 't': 105, 'y': 120, 'u': 136, 'i': 153,
    'o': 171, 'p': 190, 'a': 210, 's': 231, 'd': 253, 'f': 276, 'g': 300, 'h': 325,
    'j': 351, 'k': 378, 'l': 406, 'z': 435, 'x': 465, 'c': 496, 'v': 528, 'b': 561, 'n': 595, 'm': 630,
};
// Satanic: a=36, b=37... z=61, 0-9=0-9
const satanicMap = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'a': 36, 'b': 37, 'c': 38, 'd': 39, 'e': 40, 'f': 41, 'g': 42, 'h': 43,
    'i': 44, 'j': 45, 'k': 46, 'l': 47, 'm': 48,
    'n': 49, 'o': 50, 'p': 51, 'q': 52, 'r': 53, 's': 54, 't': 55,
    'u': 56, 'v': 57, 'w': 58, 'x': 59, 'y': 60, 'z': 61,
};
// Standard: a=1, b=2... i=9, j=10, k=20, l=30, m=40, n=50, o=60, p=70, q=80, r=90, s=100, t=200, u=300, v=400, w=500, x=600, y=700, z=800, 0-9=0-9
const standardMap = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8, 'i': 9,
    'j': 10, 'k': 20, 'l': 30, 'm': 40,
    'n': 50, 'o': 60, 'p': 70, 'q': 80, 'r': 90, 's': 100, 't': 200,
    'u': 300, 'v': 400, 'w': 500, 'x': 600, 'y': 700, 'z': 800,
};
// Reduction: 1-9 repeating pattern, 0-9=0-9
// a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8, i=9, j=1, k=2, l=3, m=4
// n=5, o=6, p=7, q=8, r=9, s=1, t=2, u=3, v=4, w=5, x=6, y=7, z=8
const reductionMap = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8, 'i': 9,
    'j': 1, 'k': 2, 'l': 3, 'm': 4,
    'n': 5, 'o': 6, 'p': 7, 'q': 8, 'r': 9, 's': 1, 't': 2,
    'u': 3, 'v': 4, 'w': 5, 'x': 6, 'y': 7, 'z': 8,
};
// Helper function to calculate cipher value
function calculateCipher(phrase, map, name) {
    const lowerPhrase = phrase.toLowerCase();
    const breakdown = [];
    let total = 0;
    for (const char of lowerPhrase) {
        const value = map[char] ?? 0;
        if (value !== 0 || map[char] !== undefined) {
            breakdown.push({ char, value });
            total += value;
        }
    }
    return { name, phrase, value: total, breakdown };
}
// Export all cipher calculators
export const ciphers = {
    alphanumericQabbala: (phrase) => calculateCipher(phrase, alphanumericQabbalaMap, 'Alphanumeric Qabbala'),
    numericQwerty: (phrase) => calculateCipher(phrase, numericQwertyMap, 'Numeric QWERTY'),
    ordinal: (phrase) => calculateCipher(phrase, ordinalMap, 'Ordinal'),
    qwerty: (phrase) => calculateCipher(phrase, qwertyMap, 'QWERTY'),
    synx: (phrase) => calculateCipher(phrase, synxMap, 'Synx'),
    alphanumericSquares: (phrase) => calculateCipher(phrase, alphanumericSquaresMap, 'AQ Squares'),
    alphanumericPrimes: (phrase) => calculateCipher(phrase, alphanumericPrimesMap, 'AQ Primes'),
    alphanumericTrigonal: (phrase) => calculateCipher(phrase, alphanumericTrigonalMap, 'AQ Trigonal'),
    numericQwertySquares: (phrase) => calculateCipher(phrase, numericQwertySquaresMap, 'NQ Squares'),
    numericQwertyPrimes: (phrase) => calculateCipher(phrase, numericQwertyPrimesMap, 'NQ Primes'),
    numericQwertyTrigonal: (phrase) => calculateCipher(phrase, numericQwertyTrigonalMap, 'NQ Trigonal'),
    satanic: (phrase) => calculateCipher(phrase, satanicMap, 'Satanic'),
    standard: (phrase) => calculateCipher(phrase, standardMap, 'Standard'),
    reduction: (phrase) => calculateCipher(phrase, reductionMap, 'Reduction'),
    // Computed ciphers (derived from base cipher values)
    vaxen: (phrase) => {
        const aqResult = ciphers.alphanumericQabbala(phrase);
        const synxResult = ciphers.synx(phrase);
        const value = synxResult.value - aqResult.value;
        return {
            name: 'Vaxen',
            phrase,
            value,
            breakdown: !phrase ? [] : [
                { char: 'Synx', value: synxResult.value },
                { char: 'AQ', value: aqResult.value },
                { char: 'Vaxen=Synx-AQ', value },
            ]
        };
    },
    unun: (phrase) => {
        const aqResult = ciphers.alphanumericQabbala(phrase);
        const synxResult = ciphers.synx(phrase);
        const value = aqResult.value + synxResult.value;
        return {
            name: 'Unun',
            phrase,
            value,
            breakdown: !phrase ? [] : [
                { char: 'AQ', value: aqResult.value },
                { char: 'Synx', value: synxResult.value },
                { char: 'Unun=AQ+Synx', value },
            ]
        };
    },
    basedAtlanteanism: (phrase) => {
        const aqResult = ciphers.alphanumericQabbala(phrase);
        const standardResult = ciphers.standard(phrase);
        const esTotal = standardResult.value - aqResult.value;
        const value = esTotal / 9;
        return {
            name: 'Based Atlanteanism',
            phrase,
            value,
            breakdown: !phrase ? [] : [
                { char: 'Standard', value: standardResult.value },
                { char: 'AQ', value: aqResult.value },
                { char: '(Std-AQ)/9', value },
            ]
        };
    },
};
// Calculate all ciphers at once
export function calculateAll(phrase) {
    return [
        ciphers.alphanumericQabbala(phrase),
        ciphers.numericQwerty(phrase),
        ciphers.ordinal(phrase),
        ciphers.qwerty(phrase),
        ciphers.synx(phrase),
        ciphers.alphanumericSquares(phrase),
        ciphers.alphanumericPrimes(phrase),
        ciphers.alphanumericTrigonal(phrase),
        ciphers.numericQwertySquares(phrase),
        ciphers.numericQwertyPrimes(phrase),
        ciphers.numericQwertyTrigonal(phrase),
        ciphers.satanic(phrase),
        ciphers.standard(phrase),
        ciphers.reduction(phrase),
        ciphers.vaxen(phrase),
        ciphers.unun(phrase),
        ciphers.basedAtlanteanism(phrase),
    ];
}
// List of all cipher names for UI
export const cipherNames = [
    'Alphanumeric Qabbala',
    'Numeric QWERTY',
    'Ordinal',
    'QWERTY',
    'Synx',
    'AQ Squares',
    'AQ Primes',
    'AQ Trigonal',
    'NQ Squares',
    'NQ Primes',
    'NQ Trigonal',
    'Satanic',
    'Standard',
    'Reduction',
    'Unun',
    'Vaxen',
    'Based Atlanteanism',
];
// Triple numbers (111, 222, 333, etc.)
export const tripleNumbers = [111, 222, 333, 444, 555, 666, 777, 888, 999, 1111, 2222, 3333, 4444, 5555, 6666, 7777, 8888, 9999];
// Cipher display name abbreviations
export const cipherDisplayNames = {
    'Alphanumeric Qabbala': 'AQ',
    'AQ Squares': 'AQ Squares ■',
    'AQ Primes': 'AQ Primes ●',
    'AQ Trigonal': 'AQ Trigonal ▲',
    'Numeric QWERTY': 'NQ',
    'NQ Squares': 'NQ Squares ■',
    'NQ Primes': 'NQ Primes ●',
    'NQ Trigonal': 'NQ Trigonal ▲',
    'Vaxen': 'Vaxen -',
    'Unun': 'Unun +',
    'Based Atlanteanism': 'Based Atlanteanism',
};
// Cipher colors for UI
export const cipherColors = {
    'Alphanumeric Qabbala': { name: 'text-stone-300', value: 'text-stone-100', bg: 'bg-stone-900' },
    'AQ Squares': { name: 'text-[#B89B6B]', value: 'text-[#D4B896]', bg: 'bg-[#2A2015]' },
    'AQ Primes': { name: 'text-[#D4B896]', value: 'text-[#EBD4B0]', bg: 'bg-[#352A1F]' },
    'AQ Trigonal': { name: 'text-[#EBD4B0]', value: 'text-[#F5E6D0]', bg: 'bg-[#403526]' },
    'Ordinal': { name: 'text-stone-200', value: 'text-stone-100', bg: 'bg-stone-700' },
    'Numeric QWERTY': { name: 'text-green-400', value: 'text-green-200', bg: 'bg-green-950' },
    'NQ Squares': { name: 'text-[#5A9B5A]', value: 'text-[#7ABD7A]', bg: 'bg-[#0F2510]' },
    'NQ Primes': { name: 'text-[#6ABD6A]', value: 'text-[#8BDF8B]', bg: 'bg-[#1A351A]' },
    'NQ Trigonal': { name: 'text-[#8BDF8B]', value: 'text-[#ABFFAB]', bg: 'bg-[#2A452A]' },
    'QWERTY': { name: 'text-lime-400', value: 'text-lime-200', bg: 'bg-lime-950' },
    'Standard': { name: 'text-[#E8A830]', value: 'text-[#F8C040]', bg: 'bg-[#3D2815]' },
    'Satanic': { name: 'text-red-500', value: 'text-red-300', bg: 'bg-red-950' },
    'Synx': { name: 'text-cyan-400', value: 'text-cyan-200', bg: 'bg-cyan-950' },
    'Reduction': { name: 'text-[#F0B840]', value: 'text-[#F8D060]', bg: 'bg-[#4A3220]' },
    'Vaxen': { name: 'text-violet-400', value: 'text-violet-200', bg: 'bg-violet-950' },
    'Unun': { name: 'text-indigo-400', value: 'text-indigo-200', bg: 'bg-indigo-950' },
    'Based Atlanteanism': { name: 'text-amber-500', value: 'text-amber-300', bg: 'bg-amber-950' },
};
// Generate a hash for phrase discovery tracking
export function generatePhraseHash(phrase) {
    // Normalize: lowercase, trim, remove extra spaces
    const normalized = phrase.toLowerCase().trim().replace(/\s+/g, ' ');
    // Simple hash function (could be replaced with crypto if needed)
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
        const char = normalized.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    return hash.toString(16); // Convert to hex
}
