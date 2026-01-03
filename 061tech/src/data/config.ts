// Site config - prices, services, etc

export const brands = {
  gpu: ['Nvidia GeForce RTX', 'AMD Radeon RX', 'Intel ARC'],
  cpu: ['Intel Core i5/i7/i9', 'AMD Ryzen 5/7/9'],
  ssd: ['Samsung', 'Crucial', 'WD'],
  ram: ['DDR4', 'DDR5'],
  motherboard: ['Intel', 'AMD', 'ASUS', 'MSI', 'Gigabyte'],
  psu: ['Corsair', 'EVGA', 'Seasonic'],
};

export const formatBrands = (brandList: string[]) => brandList.join(', ');

export const pricing = {
  hardware: {
    diagnostics: '€40-65',
    componentReplacement: '€50-100 + parts',
    deepCleaning: '€40-65',
    screenReplacement: 'Coming Soon',
  },
  upgrades: {
    ssd: '€60-90 + parts',
    ram: '€40-60 + parts',
    gpu: '€60-100 + parts',
    cpu: '€80-120 + parts',
    motherboard: '€100-150 + parts',
    psu: '€50-80 + parts',
  },
  builds: {
    caseSwap: '€80-120',
    customPcBuild: '€100-200',
    fullOverhaul: '€150-250 + parts',
  },
  software: {
    virusRemoval: '€60-80',
    windowsReinstall: '€65-100',
    performanceTuneup: '€30-40',
    softwareInstall: '€30-80',
  },
  data: {
    recoveryBasic: '€80-120',
    recoveryAdvanced: '€120-200',
    migration: '€50-80',
    backupSetup: '€40-50',
  },
  remote: {
    videoDiagnosis: '€20',
    securityHardening: '€20-40',
    remoteTuneup: '€30-40',
    softwareSetup: '€30-60',
    ongoingSupport: '€30/hr',
  },
  packages: {
    basic: 'Repair cost only',
    standard: 'Repair + €50',
    premium: 'Repair + €100',
  },
  courier: {
    laptop: { city: '€30-40', county: '€40-50' },
    desktop: { city: '€50-60', county: '€60-70' },
  },
};

export const turnaround = {
  quick: '1-2 days',
  medium: '2-3 days',
  longer: '3-5 days',
  dataRecovery: '1-3 days',
  dataRecoveryAdvanced: '3-5 days',
};

export const services = {
  hardware: [
    { service: 'Hardware Diagnostics', desc: 'Full system assessment to identify the problem', price: pricing.hardware.diagnostics, time: turnaround.quick },
    { service: 'Component Replacement', desc: 'Fans, batteries, power jacks, ports, DC connectors', price: pricing.hardware.componentReplacement, time: turnaround.medium },
    { service: 'Deep Cleaning', desc: 'Internal dust removal, thermal paste replacement', price: pricing.hardware.deepCleaning, time: turnaround.quick },
    { service: 'Screen Replacement', desc: 'Laptop LCD/LED panel replacement', price: pricing.hardware.screenReplacement, time: '-', comingSoon: true },
  ],
  upgrades: [
    { service: 'SSD Upgrade', desc: `Replace slow HDD with fast SSD (${formatBrands(brands.ssd)}). Includes data migration.`, price: pricing.upgrades.ssd, time: turnaround.quick },
    { service: 'RAM Upgrade', desc: `Add more memory for better multitasking (${formatBrands(brands.ram)})`, price: pricing.upgrades.ram, time: turnaround.quick },
    { service: 'GPU Upgrade', desc: `Graphics card upgrade - ${formatBrands(brands.gpu)}`, price: pricing.upgrades.gpu, time: turnaround.quick },
    { service: 'CPU Upgrade', desc: `Processor upgrade - ${formatBrands(brands.cpu)}`, price: pricing.upgrades.cpu, time: turnaround.medium },
    { service: 'Motherboard Upgrade', desc: `New motherboard install with component migration (${formatBrands(brands.motherboard)})`, price: pricing.upgrades.motherboard, time: turnaround.medium },
    { service: 'Power Supply (PSU)', desc: `Replace or upgrade PSU - ${formatBrands(brands.psu)}. Essential for GPU upgrades.`, price: pricing.upgrades.psu, time: turnaround.quick },
  ],
  builds: [
    { service: 'Case Swap', desc: 'Move all your components to a new case. Better airflow, aesthetics, or space.', price: pricing.builds.caseSwap, time: turnaround.medium },
    { service: 'Custom PC Build', desc: 'I build your PC from parts you provide or spec out. Full assembly and testing.', price: pricing.builds.customPcBuild, time: turnaround.longer },
    { service: 'Full System Overhaul', desc: 'Multiple upgrades (SSD + RAM + GPU + more) with clean Windows install', price: pricing.builds.fullOverhaul, time: turnaround.longer },
  ],
  software: [
    { service: 'Virus & Malware Removal', desc: 'Deep clean, remove infections, restore security', price: pricing.software.virusRemoval, time: turnaround.quick },
    { service: 'Windows Reinstall', desc: 'Fresh Windows 10/11 install, drivers, essential software', price: pricing.software.windowsReinstall, time: turnaround.quick },
    { service: 'Performance Tune-up', desc: 'Remove bloatware, optimise startup, clean registry', price: pricing.software.performanceTuneup, time: turnaround.quick },
    { service: 'Software Installation', desc: 'Office 365, browsers, email clients, printers, etc.', price: pricing.software.softwareInstall, time: turnaround.quick },
  ],
  data: [
    { service: 'Data Recovery (Basic)', desc: 'Recover files from accessible drives', price: pricing.data.recoveryBasic, time: turnaround.dataRecovery },
    { service: 'Data Recovery (Advanced)', desc: 'Recover from failing or corrupted drives', price: pricing.data.recoveryAdvanced, time: turnaround.dataRecoveryAdvanced },
    { service: 'Data Migration', desc: 'Transfer files, settings, emails to new PC', price: pricing.data.migration, time: turnaround.quick },
    { service: 'Backup Setup', desc: 'Configure automatic backups (cloud or local)', price: pricing.data.backupSetup, time: turnaround.quick },
  ],
  remote: [
    { service: 'Video Diagnosis', desc: "Quick video call to figure out what's wrong and what it'll cost", price: pricing.remote.videoDiagnosis, note: 'Credited toward repair' },
    { service: 'Security Hardening', desc: 'VPN setup, password manager, secure DNS, browser privacy', price: pricing.remote.securityHardening, note: '' },
    { service: 'Remote Tune-up', desc: 'Bloatware removal, startup optimisation, general cleanup', price: pricing.remote.remoteTuneup, note: '' },
    { service: 'Software Setup', desc: 'Install and configure programs remotely', price: pricing.remote.softwareSetup, note: '' },
    { service: 'Ongoing Support', desc: 'Remote help when you need it - billed per hour', price: pricing.remote.ongoingSupport, note: 'Flat hourly rate' },
  ],
};

export const packages = [
  { name: 'Basic', desc: 'Just the repair, nothing extra', includes: ['Repair service only', 'Standard warranty'], price: pricing.packages.basic },
  { name: 'Standard', desc: 'Most popular - repair plus protection', includes: ['Repair service', 'Security hardening', 'Performance tune-up', '30-day warranty'], price: pricing.packages.standard, popular: true },
  { name: 'Premium', desc: 'Complete peace of mind', includes: ['Repair service', 'Security hardening', 'Performance tune-up', 'Backup setup', '1 hour remote support', '60-day warranty'], price: pricing.packages.premium },
];

export const quickLinks = [
  { label: "Won't turn on", anchor: "#hardware" },
  { label: "Running slow", anchor: "#upgrades" },
  { label: "Virus/pop-ups", anchor: "#software" },
  { label: "Lost files", anchor: "#data" },
  { label: "Upgrade parts", anchor: "#upgrades" },
  { label: "Custom PC build", anchor: "#builds" },
  { label: "Remote help", anchor: "#remote" },
];

export const seoKeywords = {
  gpu: formatBrands(brands.gpu),
  cpu: formatBrands(brands.cpu),
  all: `${formatBrands(brands.gpu)}, ${formatBrands(brands.cpu)}, SSD, RAM`,
};

export const homepage = {
  problems: [
    { symptom: "Won't turn on", price: '€100', priceFrom: true, desc: 'No power, no lights, dead battery', service: 'Hardware Diagnosis & Repair' },
    { symptom: 'Running really slow', price: '€60', priceFrom: true, desc: 'Takes ages to start, freezes constantly', service: 'SSD Upgrade or Tune-up' },
    { symptom: 'Virus or pop-ups', price: '€60', priceFrom: true, desc: 'Warnings, strange behaviour, hijacked browser', service: 'Virus Removal & Security' },
    { symptom: 'Lost important files', price: '€80', priceFrom: true, desc: 'Accidentally deleted, drive not showing', service: 'Data Recovery' },
    { symptom: 'Need a fresh start', price: '€65', priceFrom: true, desc: 'Too cluttered, want it like new again', service: 'Windows Reinstall' },
    { symptom: 'Something else?', price: '€20', priceFrom: false, desc: "Not sure what's wrong - let's figure it out", service: 'Video Diagnosis', highlight: true },
  ],
  upgrades: [
    { name: 'SSD Upgrade', price: '€60', priceFrom: true, desc: 'The #1 speed boost for any computer' },
    { name: 'RAM Upgrade', price: '€40', priceFrom: true, desc: 'More memory for multitasking' },
    { name: 'GPU Upgrade', price: '€60', priceFrom: true, desc: `Better graphics - ${brands.gpu.join(', ')}` },
    { name: 'Custom PC Build', price: '€100', priceFrom: true, desc: 'I build it, you game on it' },
  ],
  remoteServices: [
    { name: 'Security Setup', price: '€30', priceFrom: true, desc: 'VPN, password manager, secure browsing' },
    { name: 'Performance Tune-up', price: '€40', priceFrom: true, desc: 'Remove bloatware, speed up startup' },
    { name: 'Software Install', price: '€40', priceFrom: true, desc: 'Office 365, email, printers' },
    { name: 'Ongoing Support', price: '€30/hr', priceFrom: false, desc: 'Remote help when you need it' },
  ],
  steps: [
    { num: 1, title: 'Book', desc: 'Online form or chat' },
    { num: 2, title: 'Collection', desc: 'Courier picks up' },
    { num: 3, title: 'Repair', desc: 'We fix it' },
    { num: 4, title: 'Return', desc: 'Delivered back' },
  ],
};
