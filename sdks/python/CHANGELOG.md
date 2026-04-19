# Changelog
All notable changes to the Python SDK will be documented in this file.

## [0.1.0] - 2026-04-19

### 🐛 Bug Fixes

- Flat N-ary trace trees with correct child order (#42) ([`1668d35`](https://github.com/Nagato-Yuzuru/predylogic/commit/1668d3586cd3c0db1650840543d60b0e178091d5))

- ⚠ **BREAKING** — Separate rule_def_name discriminator from rule parameters ([`699d33c`](https://github.com/Nagato-Yuzuru/predylogic/commit/699d33cf49b776362ca3592944c1b6541efdd593))


### 📚 Documentation

- Add cautionary note about design notes validity ([`9a3e9ab`](https://github.com/Nagato-Yuzuru/predylogic/commit/9a3e9aba35225292618596cb9c1264c34d2a1133))

- Enhance README with decorator and composition details ([`98e9642`](https://github.com/Nagato-Yuzuru/predylogic/commit/98e9642560ea035addbb60508302a27a9e83240b))

- Refine formatting, enhance examples, and add roadmap ([`1b666c9`](https://github.com/Nagato-Yuzuru/predylogic/commit/1b666c9d39823c1f08c61a12bdcf484a60f95889))

## [0.0.2] - 2026-02-05

### 📚 Documentation

- Add PyPI Python version badge to project badges ([`98f72d8`](https://github.com/Nagato-Yuzuru/predylogic/commit/98f72d821f6702fc0708e028ac632515288631f4))

- Add comprehensive quick start guide for Predylogic ([`cf96123`](https://github.com/Nagato-Yuzuru/predylogic/commit/cf96123bfeed46727fed0c4833cb48cc8f86ba14))

- Improve formatting and clarity in quick start guide ([`eac265e`](https://github.com/Nagato-Yuzuru/predylogic/commit/eac265e32518a64743486de2dc37968a8acc8355))

- Improve formatting and clarity in quick start guide ([`890bc3f`](https://github.com/Nagato-Yuzuru/predylogic/commit/890bc3fb4b906243673860ae14b36bc43c24b8a7))


### 🚀 Features

- Add SchemaGenerator for JSON Schema creation ([`94c849f`](https://github.com/Nagato-Yuzuru/predylogic/commit/94c849f3fb940010daa198fefcb7a9653eef0a6e))

- Enhance RuleSetManifest and add error handling for cyclic rule definitions ([`efc172b`](https://github.com/Nagato-Yuzuru/predylogic/commit/efc172b92b3a298b2f8607e3f6e3626d1f0d636f))

- Introduce ComposablePredicate and enhance predicate functionality ([`874c909`](https://github.com/Nagato-Yuzuru/predylogic/commit/874c9094e6dd837ab6d0f27180c0577d263c0c54))

- Add custom error classes for rule engine ([`6e0c1fd`](https://github.com/Nagato-Yuzuru/predylogic/commit/6e0c1fd9145b20468966cf7a9593337a81632b5c))

- Enhance schema generation with improved type handling and factory creation ([`1fcfc23`](https://github.com/Nagato-Yuzuru/predylogic/commit/1fcfc23cb9c1612e33db517172902ea81bc7903c))

- Simplify register addition by removing name parameter ([`84a8bc9`](https://github.com/Nagato-Yuzuru/predylogic/commit/84a8bc9d5083c059c8d708503c6e84732e83af12))


### 🚜 Refactor & Architecture

- Reorganize schema and rule engine imports ([`e580003`](https://github.com/Nagato-Yuzuru/predylogic/commit/e580003a9eb526519e1f325fe824ab21151982f1))

## [0.0.1] - 2026-01-30

### ⚡ Performance Optimizations

- Add optimisation for non-left-skewed trees using all/any in the collect chain ([`458b8b7`](https://github.com/Nagato-Yuzuru/predylogic/commit/458b8b7a817d362b6629e261d3925587012cb543))


### 🐛 Bug Fixes

- Add explicit name attribute to predicates ([`827191a`](https://github.com/Nagato-Yuzuru/predylogic/commit/827191a9d8711fcdd5a9397d636c090afe1e4e0d))

- Update trace operator to use "leaf" for leaf nodes ([`b6c7b9b`](https://github.com/Nagato-Yuzuru/predylogic/commit/b6c7b9bbd36b40fe47785f7261fa6cfd4f91ab17))


### 📚 Documentation

- Enhance documentation with detailed overview and contributing guidelines ([`c06048b`](https://github.com/Nagato-Yuzuru/predylogic/commit/c06048bdcd6be9cc8f311699c33b7840190c9914))

- Add architectural documentation and ADRs ([`416199f`](https://github.com/Nagato-Yuzuru/predylogic/commit/416199f4c46dc39271560c5cc753361382b60b2c))

- Add architectural documentation and ADRs ([`2b99bec`](https://github.com/Nagato-Yuzuru/predylogic/commit/2b99bec552100d8e282c7582e0d973fbec911fe6))

- Rename is_adult function to is_age_over_threshold ([`9a60836`](https://github.com/Nagato-Yuzuru/predylogic/commit/9a6083666058cd0e0812db46afd9bda5814c001d))

- Enhance documentation for predicate class and methods ([`d44fa5f`](https://github.com/Nagato-Yuzuru/predylogic/commit/d44fa5fbb7036243034ab0a0f4dfcc103783cb24))


### 🚀 Features

- Implement predicate and registry system with error ([`b597259`](https://github.com/Nagato-Yuzuru/predylogic/commit/b59725982e48c483dc5eb9277a63f70f1083979e))

- Add all and any class methods for predicates ([`1d999fa`](https://github.com/Nagato-Yuzuru/predylogic/commit/1d999fad2a4022e4736f8ee95a338fa1a535a95e))


### 🚜 Refactor & Architecture

- Refactor registry-related APIs and write tests ([`f3a0f15`](https://github.com/Nagato-Yuzuru/predylogic/commit/f3a0f15014d2663ce0dd0db41b25e88b5a02a48f))

- Enhance predicate structure and add trace functionality ([`2fda490`](https://github.com/Nagato-Yuzuru/predylogic/commit/2fda49022dcd0d08efdf77d99be6d450d1aacc02))

- Simplify predicate execution and enhance compiler ([`3a07b77`](https://github.com/Nagato-Yuzuru/predylogic/commit/3a07b778ecb3cb029113b2352221b948bd4c82e5))

- Optimize predicate execution and enhance caching mechanism ([`97bb4fa`](https://github.com/Nagato-Yuzuru/predylogic/commit/97bb4fa46199e7ac16afdaa653375d733de3bdb8))

- Streamline predicate operations and enhance type handling ([`5943826`](https://github.com/Nagato-Yuzuru/predylogic/commit/5943826d1e88d648c19170b4dd00e86fbd9831df))

